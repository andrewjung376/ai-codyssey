import json

import pytest

from main import app
from routers.chat import llm_dependency
from services import agent
from services.tools import TOOL_NAMES, TOOL_SPECS, ToolError, execute_tool


def call(name, args, call_id="c1"):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class ScriptedClient:
    """미리 정한 assistant 응답을 차례로 돌려주고, 받은 요청을 기록한다."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def chat(self, messages, tools=None, tool_choice=None):
        self.requests.append({"messages": [dict(m) for m in messages], "tool_choice": tool_choice})
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class Providers:
    def __init__(self, *providers):
        self.providers = list(providers)


@pytest.fixture
def use_llm():
    def _use(*providers):
        llm = Providers(*providers)
        app.dependency_overrides[llm_dependency] = lambda: llm
        return llm
    return _use


def answer(text):
    return {"role": "assistant", "content": text}


def tool_turn(*calls):
    return {"role": "assistant", "content": None, "tool_calls": list(calls)}


# ── 도구 스키마·실행 ─────────────────────────
def test_every_tool_requires_reason():
    assert TOOL_NAMES == {"get_data_summary", "get_data_range", "get_monthly_stats",
                          "list_conversations", "get_conversation"}
    for spec in TOOL_SPECS:
        assert "reason" in spec["function"]["parameters"]["required"]


def test_execute_tools(repo):
    r = execute_tool(repo, "get_data_range", {"start_date": "2026-01-03", "end_date": "2026-01-05"})
    assert [p["date"] for p in r["points"]] == ["2026-01-03", "2026-01-04", "2026-01-05"] and not r["truncated"]
    assert execute_tool(repo, "get_data_summary", {})["count"] == 25
    assert execute_tool(repo, "get_monthly_stats", {"month": "2026-01"})["months"][0]["max"] == 125
    assert execute_tool(repo, "get_monthly_stats", {"month": "2025-12"})["months"] == []
    conv = repo.create_conversation("t", [{"role": "user", "content": "x"}])
    assert execute_tool(repo, "list_conversations", {})["conversations"][0]["id"] == conv["id"]
    assert execute_tool(repo, "get_conversation", {"conversation_id": conv["id"]})["messages"][0]["content"] == "x"


@pytest.mark.parametrize("name,args", [
    ("get_data_range", {"start_date": "2026-13-01", "end_date": "2026-01-05"}),
    ("get_data_range", {"start_date": "2026-01-05", "end_date": "2026-01-01"}),
    ("get_monthly_stats", {"month": "2026-1"}),
    ("get_conversation", {"conversation_id": "nope"}),
    ("delete_everything", {}),
])
def test_execute_tool_errors(repo, name, args):
    with pytest.raises(ToolError):
        execute_tool(repo, name, args)


def test_range_truncated(repo, monkeypatch):
    from services import tools
    monkeypatch.setattr(tools, "RANGE_LIMIT", 5)
    r = execute_tool(repo, "get_data_range", {"start_date": "2026-01-01", "end_date": "2026-01-31"})
    assert r["count"] == 25 and r["truncated"] and len(r["points"]) == 5


# ── /api/chat/tools ─────────────────────────
def test_tool_chat_calls_tool_then_answers(client, use_llm):
    cody = ScriptedClient(
        tool_turn(call("get_data_range", {"start_date": "2026-01-02", "end_date": "2026-01-03",
                                          "reason": "기간이 정해진 질문이라 해당 기간만 조회"})),
        answer("1월 2일 102, 1월 3일 103입니다."),
    )
    use_llm(("cody", cody))
    res = client.post("/api/chat/tools", json={"message": "1월 2~3일 값은?"})
    assert res.status_code == 200
    out = res.json()
    assert out["reply"] == "1월 2일 102, 1월 3일 103입니다." and out["key_source"] == "cody"
    assert out["tool_calls"] == [{
        "round": 1, "name": "get_data_range", "arguments": {"start_date": "2026-01-02", "end_date": "2026-01-03"},
        "reason": "기간이 정해진 질문이라 해당 기간만 조회", "ok": True, "result_summary": "2026-01-02~2026-01-03 2개"}]

    # 두 번째 요청에는 assistant 의 tool_calls 와 그에 대한 tool 결과가 짝을 이뤄 들어간다
    second = cody.requests[1]["messages"]
    assert second[0]["role"] == "system" and "도구" in second[0]["content"]
    assert second[-2]["role"] == "assistant" and second[-2]["tool_calls"][0]["id"] == "c1"
    assert second[-1]["role"] == "tool" and second[-1]["tool_call_id"] == "c1"
    assert '"value": 102.0' in second[-1]["content"]
    # 컨텍스트 주입 방식과 달리 시스템 프롬프트에는 데이터 요약이 없다
    assert "총 레코드" not in second[0]["content"]

    conv = client.get(f"/api/conversations/{out['conversation_id']}").json()
    assert conv["messages"][1]["tool_calls"][0]["name"] == "get_data_range"
    assert "tool_calls" not in conv["messages"][0]


def test_tool_chat_answers_without_tools(client, use_llm):
    use_llm(("cody", ScriptedClient(answer("안녕하세요"))))
    out = client.post("/api/chat/tools", json={"message": "안녕"}).json()
    assert out["tool_calls"] == [] and out["reply"] == "안녕하세요"


def test_tool_errors_are_returned_to_model(client, use_llm):
    cody = ScriptedClient(
        tool_turn(call("get_data_range", {"start_date": "어제", "end_date": "2026-01-03", "reason": "r"}, "a"),
                  call("no_such_tool", {"reason": "r"}, "b")),
        tool_turn(call("get_data_summary", {"reason": "요약으로 대신"}, "c")),
        answer("요약 기준으로 답합니다."),
    )
    use_llm(("cody", cody))
    out = client.post("/api/chat/tools", json={"message": "x"}).json()
    assert [(t["round"], t["name"], t["ok"]) for t in out["tool_calls"]] == [
        (1, "get_data_range", False), (1, "no_such_tool", False), (2, "get_data_summary", True)]
    assert "YYYY-MM-DD" in out["tool_calls"][0]["result_summary"]
    tool_msgs = [m for m in cody.requests[1]["messages"] if m["role"] == "tool"]
    assert len(tool_msgs) == 2 and all('"error"' in m["content"] for m in tool_msgs)


def test_bad_json_arguments(client, use_llm):
    bad = {"id": "z", "type": "function", "function": {"name": "get_data_summary", "arguments": "{oops"}}
    use_llm(("cody", ScriptedClient(tool_turn(bad), answer("ok"))))
    out = client.post("/api/chat/tools", json={"message": "x"}).json()
    assert out["tool_calls"][0]["ok"] is False and out["reply"] == "ok"


def test_round_limit_forces_answer(client, use_llm):
    loops = [tool_turn(call("get_data_summary", {"reason": "r"}, f"c{i}")) for i in range(agent.MAX_ROUNDS)]
    cody = ScriptedClient(*loops, answer("지금까지 조회한 결과로 답합니다."))
    use_llm(("cody", cody))
    out = client.post("/api/chat/tools", json={"message": "x"}).json()
    assert len(out["tool_calls"]) == agent.MAX_ROUNDS
    assert cody.requests[-1]["tool_choice"] == "none"
    assert out["reply"].startswith("지금까지")


def test_falls_back_to_next_provider_from_scratch(client, use_llm):
    cody = ScriptedClient(tool_turn(call("get_data_summary", {"reason": "r"})), RuntimeError("401"))
    openai = ScriptedClient(answer("openai 답"))
    use_llm(("cody", cody), ("openai", openai))
    out = client.post("/api/chat/tools", json={"message": "x"}).json()
    assert out["key_source"] == "openai" and out["reply"] == "openai 답"
    assert out["tool_calls"] == []  # 실패한 공급자의 기록은 남기지 않는다
    assert [m["role"] for m in openai.requests[0]["messages"]] == ["system", "user"]


def test_all_providers_fail_returns_502(client, use_llm):
    use_llm(("cody", ScriptedClient(RuntimeError("x"))), ("openai", ScriptedClient(answer(""))))
    assert client.post("/api/chat/tools", json={"message": "x"}).status_code == 502


def test_tool_chat_continues_conversation(client, use_llm):
    cody = ScriptedClient(answer("첫 답"), answer("둘째 답"))
    use_llm(("cody", cody))
    first = client.post("/api/chat/tools", json={"message": "첫 질문"}).json()
    client.post("/api/chat/tools", json={"message": "둘째", "conversation_id": first["conversation_id"]})
    roles = [m["role"] for m in cody.requests[1]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert client.post("/api/chat/tools", json={"message": "x", "conversation_id": "nope"}).status_code == 404


# ── GET /api/data 기간 필터 ──────────────────
def test_data_range_filter(client):
    rows = client.get("/api/data", params={"start": "2026-01-10", "end": "2026-01-12"}).json()
    assert [r["date"] for r in rows] == ["2026-01-10", "2026-01-11", "2026-01-12"]
    assert len(client.get("/api/data", params={"start": "2026-01-20"}).json()) == 6
    assert client.get("/api/data", params={"start": "2026-01-12", "end": "2026-01-10"}).status_code == 422
    assert client.get("/api/data", params={"start": "bad"}).status_code == 422
