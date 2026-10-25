"""도구 모드 채팅 (보너스 5.1): GPT가 필요한 데이터를 도구로 직접 골라 조회한 뒤 답한다.

/api/chat(컨텍스트 주입)과의 차이
- /api/chat       : 서버가 요약 전체를 미리 시스템 프롬프트에 넣는다.
- /api/chat/tools : 시스템 프롬프트에는 데이터가 없고, 모델이 질문에 맞는 도구만 골라 호출한다.

흐름
  1) [시스템 + 이전 대화 + 질문] 과 TOOL_SPECS 를 보낸다.
  2) 응답에 tool_calls 가 있으면 각 도구를 실행해 role=tool 메시지로 돌려주고 다시 보낸다.
  3) tool_calls 없이 답이 오면 종료한다. MAX_ROUNDS 를 넘으면 도구 없이 답하게 한다.
  4) 공급자(Cody → OpenAI) 중 하나가 도중에 실패하면, 다음 공급자로 처음부터 다시 한다.
     (공급자마다 tool_call id 체계가 달라 중간부터 이어 붙이지 않는다)
"""

import datetime as dt
import json
import logging

from core.config import settings
from services.chat import TITLE_LEN, ConversationNotFound
from services.repository import Repository
from services.tools import TOOL_SPECS, ToolError, execute_tool, summarize_result

log = logging.getLogger(__name__)

MAX_ROUNDS = 4
TOOL_RESULT_MAX = 12000  # 모델에 돌려주는 도구 결과 JSON 최대 글자 수

SYSTEM_TOOLS = """당신은 사용자의 시계열 데이터({dataset}, 단위 {unit})를 다루는 데이터 분석 비서입니다.
오늘 날짜는 {today} 입니다.

- 데이터에 관한 질문은 추측하지 말고 반드시 도구로 조회한 결과에 근거해 답하세요.
- 질문에 필요한 도구만 고르고, 기간이 정해진 질문은 get_data_range 로 그 기간만 조회하세요.
- "마지막 주", "최근", "요즘"처럼 범위가 모호하면 되묻지 말고 합리적인 기간으로 해석해 바로 조회한 뒤,
  답변 첫머리에 어떤 기간으로 해석했는지 밝히세요. (예: "9월 마지막 주"는 9월 마지막 거래일이 속한 주)
- 도구를 부를 때 reason 에 왜 그 도구가 필요한지 한 문장으로 적으세요.
- 최종 답은 한국어로 간결하게, 구체적인 수치·날짜를 들어 작성하세요. 투자 권유가 아닌 데이터 해석입니다."""


class ToolLoopError(RuntimeError):
    pass


def _system_prompt() -> str:
    return SYSTEM_TOOLS.format(dataset=settings.dataset_name, unit=settings.dataset_unit,
                               today=dt.date.today().isoformat())


def _run_tool_call(repo: Repository, call: dict, round_no: int) -> tuple[dict, dict]:
    """도구 하나를 실행해 (role=tool 메시지, 호출 기록)을 돌려준다."""
    fn = call.get("function", {})
    name = fn.get("name", "")
    try:
        args = json.loads(fn.get("arguments") or "{}")
        if not isinstance(args, dict):
            raise ValueError
    except ValueError:  # JSONDecodeError 포함
        args, result, ok = {}, {"error": "arguments 는 올바른 JSON 객체여야 합니다."}, False
    else:
        try:
            result, ok = execute_tool(repo, name, args), True
        except ToolError as e:
            result, ok = {"error": str(e)}, False

    reason = str(args.pop("reason", "") or "")
    trace = {"round": round_no, "name": name, "arguments": args, "reason": reason, "ok": ok,
             "result_summary": summarize_result(name, result) if ok else result["error"]}
    content = json.dumps(result, ensure_ascii=False, default=str)[:TOOL_RESULT_MAX]
    return {"role": "tool", "tool_call_id": call.get("id", ""), "content": content}, trace


def _tool_loop(client, repo: Repository, messages: list[dict]) -> tuple[str, list[dict]]:
    messages = list(messages)
    traces: list[dict] = []
    for round_no in range(1, MAX_ROUNDS + 1):
        msg = client.chat(messages, tools=TOOL_SPECS, tool_choice="auto")
        calls = msg.get("tool_calls") or []
        if not calls:
            text = (msg.get("content") or "").strip()
            if not text:
                raise ToolLoopError("모델이 빈 답을 돌려줬습니다.")
            return text, traces
        # assistant 의 tool_calls 메시지를 그대로 이어 붙여야 다음 요청에서 tool 결과와 짝이 맞는다
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for call in calls:
            tool_msg, trace = _run_tool_call(repo, call, round_no)
            messages.append(tool_msg)
            traces.append(trace)

    # 도구 호출이 계속 이어지면 지금까지 조회한 결과로 답하게 한다
    msg = client.chat(messages, tools=TOOL_SPECS, tool_choice="none")
    text = (msg.get("content") or "").strip()
    if not text:
        raise ToolLoopError(f"도구 호출이 {MAX_ROUNDS}회를 넘었는데 답이 없습니다.")
    return text, traces


def run_tool_chat(repo: Repository, llm, message: str, conversation_id: str | None) -> dict:
    history: list[dict] = []
    if conversation_id:
        conv = repo.get_conversation(conversation_id)
        if not conv:
            raise ConversationNotFound(conversation_id)
        history = [{"role": m["role"], "content": m["content"]} for m in conv["messages"]]
        history = history[-settings.chat_history_limit:]

    messages = [{"role": "system", "content": _system_prompt()}, *history, {"role": "user", "content": message}]

    last_error: Exception | None = None
    for source, client in llm.providers:
        try:
            reply, traces = _tool_loop(client, repo, messages)
            break
        except Exception as e:  # 401·타임아웃·빈 답 등 → 다음 공급자로 처음부터
            last_error = e
            status = getattr(getattr(e, "response", None), "status_code", None)
            log.warning("도구 모드 실패 [%s] status=%s %s", source, status, type(e).__name__)
    else:
        raise last_error or ToolLoopError("사용할 수 있는 LLM 공급자가 없습니다.")

    # 대화 자동 저장 (assistant 메시지에 호출 기록을 함께 남겨 불러올 때도 보이게 한다)
    new_msgs = [{"role": "user", "content": message},
                {"role": "assistant", "content": reply, "tool_calls": traces}]
    if conversation_id:
        repo.append_messages(conversation_id, new_msgs)
    else:
        title = message if len(message) <= TITLE_LEN else message[:TITLE_LEN] + "…"
        conversation_id = repo.create_conversation(title, new_msgs)["id"]

    return {"conversation_id": conversation_id, "reply": reply, "key_source": source, "tool_calls": traces}
