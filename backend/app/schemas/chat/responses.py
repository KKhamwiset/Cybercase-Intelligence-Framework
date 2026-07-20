from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ThreadStatus = Literal[
    "idle",
    "processing",
    "awaiting_followup",
    "failed",
]

MessageRole = Literal["user", "assistant"]

RunStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
]

RunOperation = Literal["query", "resume"]


class ChatThreadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: ThreadStatus
    created_at: datetime
    updated_at: datetime


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    thread_id: UUID
    ordinal: int
    role: MessageRole
    content: str
    retrieval_context_id: str | None
    metadata_json: dict[str, Any]
    created_at: datetime


class ChatThreadDetail(ChatThreadRead):
    messages: list[ChatMessageRead] = Field(default_factory=list)


class ChatRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    thread_id: UUID
    request_message_id: UUID
    operation: RunOperation
    status: RunStatus
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ChatMessageAccepted(BaseModel):
    message: ChatMessageRead
    run: ChatRunRead