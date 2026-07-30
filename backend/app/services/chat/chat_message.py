import hashlib
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatRun, ChatThread
from app.schemas.chat import ChatMessageCreate, ChatMessageRead
from app.services.chat.followup_policy import build_clarified_query


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

            rag_query = request.content
            skip_followup_policy = thread.status == "awaiting_followup"
            if skip_followup_policy:
                history_result = await self.db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.thread_id == thread.id)
                    .order_by(ChatMessage.ordinal.desc())
                    .limit(2)
                )
                history = history_result.scalars().all()
                clarification = next(
                    (
                        message
                        for message in history
                        if message.role == "assistant"
                    ),
                    None,
                )
                original = next(
                    (
                        message
                        for message in history
                        if message.role == "user"
                        and (
                            clarification is None
                            or message.ordinal < clarification.ordinal
                        )
                    ),
                    None,
                )
                rag_query = build_clarified_query(
                    original_user_content=original.content if original else "",
                    clarification_question=(
                        clarification.content if clarification else ""
                    ),
                    current_answer=request.content,
                )

            # Legacy session IDs are historical only. Every new chat run uses
            # the current completed-response RAG query boundary.
            thread.active_rag_session_id = None

            ordinal = thread.next_message_ordinal
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
                    "skip_followup_policy": skip_followup_policy,
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
