import hashlib
from dataclasses import dataclass
from typing import Sequence
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatRun, ChatThread
from app.schemas.chat import ChatMessageCreate, ChatMessageRead
from app.services.chat.followup_policy import (
    ClarificationExchange,
    build_clarified_query,
)


@dataclass(frozen=True)
class ClarificationChain:
    root_ordinal: int
    original_user_content: str
    exchanges: tuple[ClarificationExchange, ...]


def _followup_root_ordinal(message: ChatMessage) -> int | None:
    metadata = message.metadata_json
    if not isinstance(metadata, dict):
        return None
    followup = metadata.get("chat_followup")
    if not isinstance(followup, dict):
        return None
    root_ordinal = followup.get("root_ordinal")
    if (
        not isinstance(root_ordinal, int)
        or isinstance(root_ordinal, bool)
        or root_ordinal < 1
    ):
        return None
    return root_ordinal


def reconstruct_clarification_chain(
    messages: Sequence[ChatMessage],
    *,
    root_ordinal: int | None = None,
    pending_answer: str | None = None,
) -> ClarificationChain | None:
    """Reconstruct one active clarification chain from persisted messages."""

    ordered = sorted(messages, key=lambda message: message.ordinal)
    if not ordered:
        return None

    latest_assistant_index = next(
        (
            index
            for index in range(len(ordered) - 1, -1, -1)
            if ordered[index].role == "assistant"
        ),
        None,
    )
    if root_ordinal is None and latest_assistant_index is not None:
        root_ordinal = _followup_root_ordinal(
            ordered[latest_assistant_index]
        )

    root_index = next(
        (
            index
            for index, message in enumerate(ordered)
            if message.role == "user" and message.ordinal == root_ordinal
        ),
        None,
    )
    if root_index is None and latest_assistant_index is not None:
        root_index = next(
            (
                index
                for index in range(latest_assistant_index - 1, -1, -1)
                if ordered[index].role == "user"
            ),
            None,
        )
    if root_index is None:
        root_index = next(
            (
                index
                for index in range(len(ordered) - 1, -1, -1)
                if ordered[index].role == "user"
            ),
            None,
        )
    if root_index is None:
        return None

    root = ordered[root_index]
    exchanges: list[ClarificationExchange] = []
    pending_question: str | None = None
    for message in ordered[root_index + 1 :]:
        if message.role == "assistant":
            pending_question = message.content
        elif message.role == "user" and pending_question is not None:
            exchanges.append(
                ClarificationExchange(
                    question=pending_question,
                    answer=message.content,
                )
            )
            pending_question = None

    if pending_question is not None and pending_answer is not None:
        exchanges.append(
            ClarificationExchange(
                question=pending_question,
                answer=pending_answer,
            )
        )

    return ClarificationChain(
        root_ordinal=root.ordinal,
        original_user_content=root.content,
        exchanges=tuple(exchanges),
    )


class ChatMessageService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_message_and_run(
        self,
        thread_id: UUID,
        request: ChatMessageCreate,
    ) -> tuple[ChatMessage, ChatRun]:
        request_fingerprint = hashlib.sha256(
            request.content.encode("utf-8")
        ).hexdigest()
        async with self.db.begin():
            statement = (
                select(ChatThread).where(ChatThread.id == thread_id).with_for_update()
            )
            result = await self.db.execute(statement)
            thread = result.scalar_one_or_none()

            if thread is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Chat thread not found",
                )
            existing_statement = select(ChatRun).where(
                ChatRun.thread_id == thread_id,
                ChatRun.idempotency_key == request.idempotency_key,
            )

            existing_result = await self.db.execute(existing_statement)
            existing_run = existing_result.scalar_one_or_none()
            if existing_run is not None:
                if existing_run.request_fingerprint != request_fingerprint:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Idempotency key was already used with different content",
                    )
                existing_message = await self.db.get(
                    ChatMessage, existing_run.request_message_id
                )
                return existing_message, existing_run

            active_run_statement = select(ChatRun).where(
                ChatRun.thread_id == thread.id,
                ChatRun.status.in_(("queued", "running")),
            )

            active_run_result = await self.db.execute(active_run_statement)
            active_run = active_run_result.scalar_one_or_none()

            if active_run is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Chat thread already has an active run",
                )

            ordinal = thread.next_message_ordinal
            rag_query = request.content
            followup_root_ordinal = ordinal
            followup_round = 0
            if thread.status == "awaiting_followup":
                history_result = await self.db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.thread_id == thread.id)
                    .order_by(ChatMessage.ordinal)
                )
                history = history_result.scalars().all()
                chain = reconstruct_clarification_chain(
                    history,
                    pending_answer=request.content,
                )
                if chain is not None:
                    followup_root_ordinal = chain.root_ordinal
                    followup_round = len(chain.exchanges)
                    rag_query = build_clarified_query(
                        original_user_content=chain.original_user_content,
                        clarification_exchanges=chain.exchanges,
                    )

            # Legacy session IDs are historical only. Every new chat run uses
            # the current completed-response RAG query boundary.
            thread.active_rag_session_id = None

            thread.next_message_ordinal += 1
            thread.status = "processing"

            message = ChatMessage(
                thread_id=thread.id,
                ordinal=ordinal,
                content=request.content,
                role="user",
            )

            self.db.add(message)

            await self.db.flush()

            run = ChatRun(
                thread_id=thread.id,
                request_message_id=message.id,
                operation="query",
                input_rag_session_id=None,
                idempotency_key=request.idempotency_key,
                request_fingerprint=request_fingerprint,
                request_payload={
                    "content": request.content,
                    "rag_query": rag_query,
                    "followup_root_ordinal": followup_root_ordinal,
                    "followup_round": followup_round,
                },
            )

            self.db.add(run)
            await self.db.flush()
            await self.db.refresh(message)
            await self.db.refresh(run)
        return message, run

    async def get_run(
        self,
        thread_id: UUID,
        run_id: UUID,
    ) -> ChatRun:
        statement = select(ChatRun).where(
            ChatRun.thread_id == thread_id, ChatRun.id == run_id
        )
        result = await self.db.execute(statement)
        run = result.scalar_one_or_none()
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat run not found",
            )
        return run

    async def list_messages(
        self,
        thread_id: UUID,
    ) -> list[ChatMessageRead]:
        statement = (
            select(ChatMessage)
            .where(ChatMessage.thread_id == thread_id)
            .order_by(ChatMessage.ordinal)
        )
        result = await self.db.execute(statement)
        return [
            ChatMessageRead.model_validate(message)
            for message in result.scalars().all()
        ]
