"""Takeout 내보내기(zip·JSON·CSV)를 읽고 각 파일의 데이터 종류를 판별한다.

폴더·파일 이름은 계정 언어에 따라 다르므로 경로에 기대지 않고 파일 내용으로 판별한다.
- 활동 기록: `time` 필드가 있는 dict 목록인 JSON
- Chrome 방문 기록(BrowserHistory): 최상위가 dict이고 `Browser History` 목록이 있는 JSON
- 내 채널 정보: `Channel ID`(또는 `채널 ID`) 컬럼이 있는 CSV
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePath

CHANNEL_ID_COLUMNS = ("Channel ID", "채널 ID")
CHANNEL_TITLE_COLUMNS = ("Channel Title (Original)", "Channel Title", "채널 제목(원본)", "채널 제목")
BROWSER_HISTORY_KEY = "Browser History"


@dataclass
class TakeoutExport:
    """업로드한 파일 하나(zip 또는 단일 파일)에서 읽어 낸 내용."""
    name: str
    activity_files: dict[str, list[dict]] = field(default_factory=dict)  # 내부 경로 → 활동 레코드
    channel: dict[str, str] | None = None  # {"id": ..., "title": ...}
    skipped: list[str] = field(default_factory=list)  # 활동 기록·채널 정보가 아니라 읽지 않은 파일
    browser_history: dict[str, list[dict]] = field(default_factory=dict)  # 내부 경로 → Chrome 방문 기록

    @property
    def record_count(self) -> int:
        files = [*self.activity_files.values(), *self.browser_history.values()]
        return sum(len(records) for records in files)


def load_takeout(source: str | Path | bytes, name: str | None = None) -> TakeoutExport:
    """파일 경로 또는 업로드된 bytes(이때는 name 필수)를 읽는다."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        data, name = path.read_bytes(), name or path.name
    else:
        if name is None:
            raise ValueError("bytes로 읽을 때는 name(파일 이름)이 필요합니다")
        data = source

    export = TakeoutExport(name=name)
    if PurePath(name).suffix.lower() == ".zip":
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for member in zf.infolist():
                if not member.is_dir():
                    _read_member(export, member.filename, zf.read(member))
    else:
        _read_member(export, name, data)
    return export


def _read_member(export: TakeoutExport, path: str, data: bytes) -> None:
    suffix = PurePath(path).suffix.lower()
    if suffix == ".json":
        try:
            parsed = json.loads(data.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            export.skipped.append(path)
            return
        if _is_activity_list(parsed):
            export.activity_files[path] = parsed
            return
        if isinstance(parsed, dict) and isinstance(parsed.get(BROWSER_HISTORY_KEY), list):
            export.browser_history[path] = parsed[BROWSER_HISTORY_KEY]
            return
    elif suffix == ".csv":
        channel = _read_channel_csv(data)
        if channel:
            export.channel = channel
            return
    export.skipped.append(path)


def _is_activity_list(data) -> bool:
    return (
        isinstance(data, list)
        and len(data) > 0
        and any(isinstance(r, dict) and "time" in r for r in data[:20])
    )


def _read_channel_csv(data: bytes) -> dict[str, str] | None:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return None
    columns = {c.strip(): c for c in reader.fieldnames}
    id_col = next((columns[c] for c in CHANNEL_ID_COLUMNS if c in columns), None)
    if id_col is None:
        return None
    title_col = next((columns[c] for c in CHANNEL_TITLE_COLUMNS if c in columns), None)
    row = next(reader, None)
    if row is None:
        return None
    return {
        "id": (row.get(id_col) or "").strip(),
        "title": (row.get(title_col) or "").strip() if title_col else "",
    }
