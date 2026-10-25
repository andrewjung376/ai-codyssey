from fastapi import APIRouter, Depends, HTTPException, status

from schemas.conversation import ConversationCreate, ConversationDetail, ConversationMeta
from services.repository import Repository, get_repository

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=ConversationDetail, response_model_exclude_none=True,
             status_code=status.HTTP_201_CREATED, summary="대화 저장")
def create_conversation(body: ConversationCreate, repo: Repository = Depends(get_repository)):
    messages = [m.model_dump(exclude_none=True) for m in body.messages]
    title = body.title or next((m["content"][:30] for m in messages if m["role"] == "user"), "새 대화")
    return repo.create_conversation(title, messages)


@router.get("", response_model=list[ConversationMeta],
            summary="대화 목록 조회 (최근 수정순, messages 미포함)")
def list_conversations(repo: Repository = Depends(get_repository)):
    return repo.list_conversations()


@router.get("/{conv_id}", response_model=ConversationDetail, response_model_exclude_none=True,
            summary="특정 대화 불러오기 (전체 messages, 도구 모드 답변은 tool_calls 포함)")
def get_conversation(conv_id: str, repo: Repository = Depends(get_repository)):
    conv = repo.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "대화를 찾을 수 없습니다.")
    return conv


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT, summary="대화 삭제")
def delete_conversation(conv_id: str, repo: Repository = Depends(get_repository)):
    if not repo.delete_conversation(conv_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "대화를 찾을 수 없습니다.")
