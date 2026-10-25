"""채팅 흐름: 요약 조회 → 시스템 프롬프트 주입 → GPT 호출 → conversations 자동 저장."""

from core.config import settings
from services.llm import LLMClient, build_system_prompt
from services.repository import Repository
from services.summary import build_summary

TITLE_LEN = 30


class ConversationNotFound(LookupError):
    pass


def run_chat(repo: Repository, llm: LLMClient, message: str, conversation_id: str | None) -> dict:
    # 1) 데이터 요약 조회 (/api/data/summary 와 같은 계산)
    summary = build_summary(repo.list_data())

    # 이어서 대화하는 경우 직전 메시지를 함께 보낸다
    history: list[dict] = []
    if conversation_id:
        conv = repo.get_conversation(conversation_id)
        if not conv:
            raise ConversationNotFound(conversation_id)
        history = [{"role": m["role"], "content": m["content"]} for m in conv["messages"]]
        history = history[-settings.chat_history_limit:]

    # 2) 요약을 시스템 프롬프트에 삽입 → 3) GPT 호출
    messages = [{"role": "system", "content": build_system_prompt(summary)}, *history,
                {"role": "user", "content": message}]
    reply, key_source = llm.complete(messages)
    reply = reply or "답변을 생성하지 못했습니다. 다시 시도해 주세요."

    # 4) 대화 자동 저장
    new_msgs = [{"role": "user", "content": message}, {"role": "assistant", "content": reply}]
    if conversation_id:
        repo.append_messages(conversation_id, new_msgs)
    else:
        title = message if len(message) <= TITLE_LEN else message[:TITLE_LEN] + "…"
        conversation_id = repo.create_conversation(title, new_msgs)["id"]

    return {
        "conversation_id": conversation_id,
        "reply": reply,
        "key_source": key_source,
        "summary_used": {k: summary[k] for k in ("period", "count", "trend")},
    }
