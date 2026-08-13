from typing import Literal

from pydantic import BaseModel, Field


class ChatThreadCreate(BaseModel):
    title: str = Field(
        default="New chat",
        min_length=1,
        max_length=255,
    )


class ChatThreadUpdate(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=255,
    )


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1)
    idempotency_key: str = Field(
        min_length=1,
        max_length=255,
    )
    action: Literal["ask", "add_case_info"] | None = None
