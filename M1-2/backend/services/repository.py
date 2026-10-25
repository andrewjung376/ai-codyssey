"""저장소 계층.

라우터/서비스는 Repository 인터페이스만 알고, 실제 저장소는 설정으로 고른다.
- FirestoreRepository: 운영 기본값. 컬렉션 `data`, `conversations`
- MemoryRepository:    Firebase 키 없이 로컬 개발·테스트할 때 (STORAGE_BACKEND=memory)

Firestore 문서 구조
  data/{auto_id}          { date: "YYYY-MM-DD", value: float, memo: str, created_at, updated_at }
  conversations/{auto_id} { title, messages: [{role, content}], message_count, created_at, updated_at }
"""

import datetime as dt
import json
import os
import threading
import uuid
from typing import Protocol

from core.config import settings

DATA = "data"
CONVERSATIONS = "conversations"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Repository(Protocol):
    def list_data(self) -> list[dict]: ...
    def find_data_by_date(self, date: str) -> dict | None: ...
    def create_data(self, item: dict) -> dict: ...
    def update_data(self, item_id: str, fields: dict) -> dict | None: ...
    def delete_data(self, item_id: str) -> bool: ...
    def bulk_insert_data(self, items: list[dict]) -> int: ...

    def list_conversations(self) -> list[dict]: ...
    def get_conversation(self, conv_id: str) -> dict | None: ...
    def create_conversation(self, title: str, messages: list[dict]) -> dict: ...
    def append_messages(self, conv_id: str, messages: list[dict]) -> dict | None: ...
    def delete_conversation(self, conv_id: str) -> bool: ...


# ── 메모리 저장소 ────────────────────────────────────────────
class MemoryRepository:
    def __init__(self):
        self._data: dict[str, dict] = {}
        self._convs: dict[str, dict] = {}

    def list_data(self) -> list[dict]:
        return sorted((dict(v) for v in self._data.values()), key=lambda d: d["date"])

    def find_data_by_date(self, date: str) -> dict | None:
        return next((dict(v) for v in self._data.values() if v["date"] == date), None)

    def create_data(self, item: dict) -> dict:
        item_id = uuid.uuid4().hex[:20]
        self._data[item_id] = {"id": item_id, **item}
        return dict(self._data[item_id])

    def update_data(self, item_id: str, fields: dict) -> dict | None:
        if item_id not in self._data:
            return None
        self._data[item_id].update(fields)
        return dict(self._data[item_id])

    def delete_data(self, item_id: str) -> bool:
        return self._data.pop(item_id, None) is not None

    def bulk_insert_data(self, items: list[dict]) -> int:
        for item in items:
            self.create_data(item)
        return len(items)

    def list_conversations(self) -> list[dict]:
        metas = [{k: v for k, v in c.items() if k != "messages"} for c in self._convs.values()]
        return sorted(metas, key=lambda c: c["updated_at"], reverse=True)

    def get_conversation(self, conv_id: str) -> dict | None:
        conv = self._convs.get(conv_id)
        return {**conv, "messages": list(conv["messages"])} if conv else None

    def create_conversation(self, title: str, messages: list[dict]) -> dict:
        conv_id = uuid.uuid4().hex[:20]
        now = _now()
        self._convs[conv_id] = {
            "id": conv_id, "title": title, "messages": list(messages),
            "message_count": len(messages), "created_at": now, "updated_at": now,
        }
        return self.get_conversation(conv_id)

    def append_messages(self, conv_id: str, messages: list[dict]) -> dict | None:
        conv = self._convs.get(conv_id)
        if not conv:
            return None
        conv["messages"].extend(messages)
        conv["message_count"] = len(conv["messages"])
        conv["updated_at"] = _now()
        return self.get_conversation(conv_id)

    def delete_conversation(self, conv_id: str) -> bool:
        return self._convs.pop(conv_id, None) is not None


# ── Firestore 저장소 ─────────────────────────────────────────
class StorageUnavailable(RuntimeError):
    """저장소 설정(서비스 계정 키 등)이 없거나 잘못됐을 때."""


def _load_credentials(raw: str):
    """FIREBASE_SERVICE_ACCOUNT_JSON 은 JSON 문자열 또는 키 파일 경로를 허용한다."""
    from firebase_admin import credentials

    if not raw:
        raise StorageUnavailable("FIREBASE_SERVICE_ACCOUNT_JSON 환경 변수가 설정되지 않았습니다.")
    try:
        if raw.lstrip().startswith("{"):
            return credentials.Certificate(json.loads(raw))
        if os.path.isfile(raw):
            return credentials.Certificate(raw)
    except ValueError as e:
        raise StorageUnavailable(f"서비스 계정 키 형식이 올바르지 않습니다: {e}") from e
    raise StorageUnavailable("FIREBASE_SERVICE_ACCOUNT_JSON 이 JSON 문자열도, 존재하는 파일 경로도 아닙니다.")


class FirestoreRepository:
    def __init__(self, service_account: str):
        import firebase_admin
        from firebase_admin import firestore

        if not firebase_admin._apps:
            firebase_admin.initialize_app(_load_credentials(service_account))
        self._db = firestore.client()

    @staticmethod
    def _doc(snap) -> dict:
        return {"id": snap.id, **snap.to_dict()}

    @staticmethod
    def _data_out(doc: dict) -> dict:
        return {k: doc.get(k) for k in ("id", "date", "value", "memo")}

    def list_data(self) -> list[dict]:
        snaps = self._db.collection(DATA).order_by("date").stream()
        return [self._data_out(self._doc(s)) for s in snaps]

    def find_data_by_date(self, date: str) -> dict | None:
        from google.cloud.firestore_v1.base_query import FieldFilter

        query = self._db.collection(DATA).where(filter=FieldFilter("date", "==", date)).limit(1)
        snaps = list(query.stream())
        return self._data_out(self._doc(snaps[0])) if snaps else None

    def create_data(self, item: dict) -> dict:
        now = _now()
        ref = self._db.collection(DATA).document()
        ref.set({**item, "created_at": now, "updated_at": now})
        return {"id": ref.id, **item}

    def update_data(self, item_id: str, fields: dict) -> dict | None:
        ref = self._db.collection(DATA).document(item_id)
        if not ref.get().exists:
            return None
        ref.update({**fields, "updated_at": _now()})
        return self._data_out(self._doc(ref.get()))

    def delete_data(self, item_id: str) -> bool:
        ref = self._db.collection(DATA).document(item_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True

    def bulk_insert_data(self, items: list[dict]) -> int:
        # Firestore 배치는 한 번에 최대 500건
        now = _now()
        for start in range(0, len(items), 400):
            batch = self._db.batch()
            for item in items[start:start + 400]:
                batch.set(self._db.collection(DATA).document(), {**item, "created_at": now, "updated_at": now})
            batch.commit()
        return len(items)

    def list_conversations(self) -> list[dict]:
        # 목록에서는 messages 필드를 읽지 않아 전송량을 줄인다
        query = (
            self._db.collection(CONVERSATIONS)
            .select(["title", "message_count", "created_at", "updated_at"])
            .order_by("updated_at", direction="DESCENDING")
        )
        return [self._doc(s) for s in query.stream()]

    def get_conversation(self, conv_id: str) -> dict | None:
        snap = self._db.collection(CONVERSATIONS).document(conv_id).get()
        return self._doc(snap) if snap.exists else None

    def create_conversation(self, title: str, messages: list[dict]) -> dict:
        now = _now()
        ref = self._db.collection(CONVERSATIONS).document()
        doc = {"title": title, "messages": messages, "message_count": len(messages),
               "created_at": now, "updated_at": now}
        ref.set(doc)
        return {"id": ref.id, **doc}

    def append_messages(self, conv_id: str, messages: list[dict]) -> dict | None:
        conv = self.get_conversation(conv_id)
        if not conv:
            return None
        merged = conv.get("messages", []) + messages
        self._db.collection(CONVERSATIONS).document(conv_id).update(
            {"messages": merged, "message_count": len(merged), "updated_at": _now()}
        )
        return self.get_conversation(conv_id)

    def delete_conversation(self, conv_id: str) -> bool:
        ref = self._db.collection(CONVERSATIONS).document(conv_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True


_repo: Repository | None = None
_repo_lock = threading.Lock()


def _create_repository() -> Repository:
    if settings.storage_backend == "memory":
        from services.seed import load_seed_items

        repo = MemoryRepository()
        repo.bulk_insert_data(load_seed_items())
        return repo
    return FirestoreRepository(settings.firebase_service_account)


def get_repository() -> Repository:
    """FastAPI 의존성. 테스트에서는 dependency_overrides 로 교체한다.

    서버가 막 켜진 뒤 첫 요청 여러 개가 동시에 오면 Firebase 앱 초기화가 두 번 일어나
    "default app already exists" 오류(500)가 날 수 있어, 잠금으로 한 번만 만든다.
    """
    global _repo
    if _repo is None:
        with _repo_lock:
            if _repo is None:
                _repo = _create_repository()
    return _repo
