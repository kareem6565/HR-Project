from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatThreadCreate(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class ChatThreadRename(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ChatThreadResponse(BaseModel):
    id: UUID
    organization_id: UUID
    title: str | None = None
    created_by_user_id: UUID | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatThreadListResponse(BaseModel):
    threads: list[ChatThreadResponse]
    total: int


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ChatToolCallResponse(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatToolResultResponse(BaseModel):
    tool: str
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None


class ChatMessageResponse(BaseModel):
    id: UUID
    chat_thread_id: UUID
    role: str
    content: str
    tool_calls: list[ChatToolCallResponse] | None = None
    tool_results: list[ChatToolResultResponse] | None = None
    workflow_run_id: UUID | None = None
    created_at: datetime


class ChatThreadDetailResponse(BaseModel):
    thread: ChatThreadResponse
    messages: list[ChatMessageResponse]


class ChatSendResponse(BaseModel):
    thread: ChatThreadResponse
    message: ChatMessageResponse
