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


class ToolCallTrace(BaseModel):
    """도구 모드에서 모델이 호출한 도구 한 건의 기록."""

    round: int = Field(..., description="몇 번째 요청에서 호출했는지 (1부터)")
    name: str
    arguments: dict
    reason: str = Field("", description="모델이 reason 인자로 밝힌 호출 이유")
    ok: bool
    result_summary: str


class Message(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=MESSAGE_MAX)
    tool_calls: list[ToolCallTrace] | None = Field(None, description="도구 모드 답변이면 호출한 도구 기록")


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
    key_source: Literal["cody", "openai"] = Field(..., description="답변에 사용한 키: cody(CODY_OPENAI_API_KEY) | openai(OPENAI_API_KEY)")
    summary_used: dict = Field(..., description="시스템 프롬프트에 주입한 요약(기간·개수·트렌드)")


class ChatToolsResponse(BaseModel):
    conversation_id: str
    reply: str
    key_source: Literal["cody", "openai"]
    tool_calls: list[ToolCallTrace] = Field(..., description="호출한 도구 순서대로 (없으면 빈 목록)")
