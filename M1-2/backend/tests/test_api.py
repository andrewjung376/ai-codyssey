def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_allowed_origins_normalized():
    from core.config import _split_origins

    assert _split_origins(" https://a.vercel.app/ , http://localhost:5500,,") == [
        "https://a.vercel.app", "http://localhost:5500"]


def test_docs_available(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    for p in ["/api/data", "/api/data/{item_id}", "/api/data/summary",
              "/api/conversations", "/api/conversations/{conv_id}", "/api/chat"]:
        assert p in paths


# ── 데이터 CRUD ──────────────────────────────
def test_data_crud(client):
    created = client.post("/api/data", json={"date": "2026-02-01", "value": 200, "memo": " 신규 "})
    assert created.status_code == 201
    item = created.json()
    assert item["memo"] == "신규"  # 앞뒤 공백 제거

    listed = client.get("/api/data").json()
    assert len(listed) == 26 and listed[-1]["date"] == "2026-02-01"

    updated = client.put(f"/api/data/{item['id']}", json={"value": 210})
    assert updated.status_code == 200
    assert updated.json() == {**item, "value": 210}

    assert client.delete(f"/api/data/{item['id']}").status_code == 204
    assert client.delete(f"/api/data/{item['id']}").status_code == 404
    assert len(client.get("/api/data").json()) == 25


def test_data_validation(client):
    bad = [
        {"date": "2026-13-01", "value": 1},
        {"date": "2026-02-01", "value": -1},
        {"date": "2026-02-01", "value": "abc"},
        {"date": "2026-02-01", "value": 1, "memo": "x" * 201},
        {"value": 1},
    ]
    for body in bad:
        assert client.post("/api/data", json=body).status_code == 422, body
    item_id = client.get("/api/data").json()[0]["id"]
    assert client.put(f"/api/data/{item_id}", json={}).status_code == 422


def test_duplicate_date_rejected(client):
    assert client.post("/api/data", json={"date": "2026-01-05", "value": 1}).status_code == 409
    first, second = client.get("/api/data").json()[:2]
    assert client.put(f"/api/data/{second['id']}", json={"date": first["date"]}).status_code == 409
    # 자기 자신의 날짜로 수정하는 것은 허용
    assert client.put(f"/api/data/{first['id']}", json={"date": first["date"], "memo": "ok"}).status_code == 200


def test_summary(client):
    s = client.get("/api/data/summary").json()
    assert s["period"] == "2026-01-01 ~ 2026-01-25"
    assert s["count"] == 25
    m = s["metrics"]
    assert m["max"] == 125 and m["max_date"] == "2026-01-25"
    assert m["min"] == 101 and m["min_date"] == "2026-01-01"
    assert m["average"] == 113
    assert s["trend"].startswith("상승")
    assert len(s["recent"]) == 10 and s["monthly"][0]["month"] == "2026-01"


def test_summary_empty(client, repo):
    for d in repo.list_data():
        repo.delete_data(d["id"])
    s = client.get("/api/data/summary").json()
    assert s["count"] == 0 and s["metrics"] is None


# ── 대화 기록 ────────────────────────────────
def test_conversations(client):
    body = {"messages": [{"role": "user", "content": "안녕"}, {"role": "assistant", "content": "반가워요"}]}
    created = client.post("/api/conversations", json=body)
    assert created.status_code == 201
    conv = created.json()
    assert conv["title"] == "안녕" and conv["message_count"] == 2

    listed = client.get("/api/conversations").json()
    assert len(listed) == 1 and "messages" not in listed[0]

    detail = client.get(f"/api/conversations/{conv['id']}").json()
    assert detail["messages"] == body["messages"]

    assert client.delete(f"/api/conversations/{conv['id']}").status_code == 204
    assert client.get(f"/api/conversations/{conv['id']}").status_code == 404


def test_conversation_validation(client):
    assert client.post("/api/conversations", json={"messages": []}).status_code == 422
    bad_role = {"messages": [{"role": "system", "content": "x"}]}
    assert client.post("/api/conversations", json=bad_role).status_code == 422


# ── 채팅 (컨텍스트 주입 + 자동 저장) ───────────
def test_chat_injects_summary_and_saves(client, llm):
    res = client.post("/api/chat", json={"message": "최근 추세가 어때?"})
    assert res.status_code == 200
    out = res.json()
    assert out["reply"] == "답변 #1"
    assert out["key_source"] == "cody"
    assert out["summary_used"]["count"] == 25

    system = llm.calls[0][0]
    assert system["role"] == "system"
    assert "2026-01-01 ~ 2026-01-25" in system["content"] and "25개" in system["content"]
    assert llm.calls[0][-1] == {"role": "user", "content": "최근 추세가 어때?"}

    conv = client.get(f"/api/conversations/{out['conversation_id']}").json()
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant"]


def test_chat_continues_conversation(client, llm):
    first = client.post("/api/chat", json={"message": "첫 질문"}).json()
    second = client.post("/api/chat", json={"message": "두번째", "conversation_id": first["conversation_id"]})
    assert second.json()["conversation_id"] == first["conversation_id"]
    # 이전 대화가 GPT 입력에 포함됨
    assert {"role": "user", "content": "첫 질문"} in llm.calls[1]
    conv = client.get(f"/api/conversations/{first['conversation_id']}").json()
    assert conv["message_count"] == 4
    assert len(client.get("/api/conversations").json()) == 1


def test_chat_reflects_data_change(client, llm):
    client.post("/api/data", json={"date": "2026-02-01", "value": 999, "memo": "이벤트"})
    client.post("/api/chat", json={"message": "최고값은?"})
    assert "999" in llm.calls[0][0]["content"] and "이벤트" in llm.calls[0][0]["content"]


def test_chat_errors(client, llm):
    assert client.post("/api/chat", json={"message": ""}).status_code == 422
    assert client.post("/api/chat", json={"message": "x", "conversation_id": "nope"}).status_code == 404

    def boom(_):
        raise RuntimeError("upstream")
    llm.complete = boom
    assert client.post("/api/chat", json={"message": "x"}).status_code == 502


def test_chat_without_key_returns_503(client, monkeypatch):
    import dataclasses

    from main import app
    from routers.chat import llm_dependency
    from services import llm as llm_module

    app.dependency_overrides.pop(llm_dependency)
    monkeypatch.setattr(llm_module, "settings",
                        dataclasses.replace(llm_module.settings, cody_api_key="", openai_api_key=""))
    llm_module._build_llm.cache_clear()
    try:
        assert client.post("/api/chat", json={"message": "x"}).status_code == 503
    finally:
        llm_module._build_llm.cache_clear()


def test_repository_created_once_under_concurrent_first_requests(monkeypatch):
    import threading
    import time

    from services import repository as repo_module

    calls = []

    def slow_create():
        calls.append(1)
        time.sleep(0.1)  # Firebase 초기화처럼 느린 생성
        return repo_module.MemoryRepository()

    monkeypatch.setattr(repo_module, "_repo", None)
    monkeypatch.setattr(repo_module, "_create_repository", slow_create)
    results = []
    threads = [threading.Thread(target=lambda: results.append(repo_module.get_repository())) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1
    assert len({id(r) for r in results}) == 1
