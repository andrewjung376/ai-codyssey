"""대화 기록·채팅 스키마.

대화 불러오기는 방식 (A)를 따른다:
- GET /api/conversations        → 목록(메타데이터만, messages 미포함)
- GET /api/conversations/{id}   → 특정 대화의 전체 messages
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MESSAGE_MAX = 4000
QUESTION_MAX = 2000
TITLE_MAX = 60


class Message(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=MESSAGE_MAX)


class ConversationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(None, max_length=TITLE_MAX)
    messages: list[Message] = Field(..., min_length=1, max_length=200)


class ConversationMeta(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: dt.datetime
    updated_at: dt.datetime


class ConversationDetail(ConversationMeta):
    messages: list[Message]


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(..., min_length=1, max_length=QUESTION_MAX, examples=["최근 추세가 어때?"])
    conversation_id: str | None = Field(None, description="이어서 대화할 대화 ID (없으면 새 대화 생성)")


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    summary_used: dict = Field(..., description="시스템 프롬프트에 주입한 요약(기간·개수·트렌드)")
