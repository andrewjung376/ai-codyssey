import logging

from fastapi import APIRouter, Depends, HTTPException, status

from schemas.conversation import ChatRequest, ChatResponse
from services.chat import ConversationNotFound, run_chat
from services.llm import LLMClient, LLMUnavailable, get_llm
from services.repository import Repository, get_repository

router = APIRouter(prefix="/api", tags=["chat"])
log = logging.getLogger(__name__)


def llm_dependency() -> LLMClient:
    try:
        return get_llm()
    except LLMUnavailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))


@router.post("/chat", response_model=ChatResponse, summary="데이터 요약을 주입한 AI 대화 (자동 저장)")
def chat(body: ChatRequest, repo: Repository = Depends(get_repository), llm: LLMClient = Depends(llm_dependency)):
    try:
        return run_chat(repo, llm, body.message, body.conversation_id)
    except ConversationNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "이어갈 대화를 찾을 수 없습니다.")
    except Exception:
        # OpenAI 오류(키 불일치, 한도 초과, 타임아웃 등)는 내부 정보 없이 502로 알린다
        log.exception("chat failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI 응답 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.")
