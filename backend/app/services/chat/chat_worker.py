'''Claim, execute, and finalize persistent background chat runs.'''

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.config import settings
from app.models.chat import ChatMessage, ChatRun, ChatThread
from app.schemas.rag import QueryResponse
from app.services.chat.followup_policy import (
    AnthropicFollowUpPolicy,
    FollowUpPolicy,
)
from app.services.chat.rag_client import RagCallFailure, request_rag


logger = logging.getLogger("app.chat")
RUN_LEASE_DURATION = timedelta(minutes=6)


@dataclass(frozen=True)
class ClaimedChatRun:
    '''Detached input needed after the claim transaction has closed.'''

    id: UUID
    operation: str
    input_rag_session_id: str | None
    content: object
    rag_query: object
    skip_followup_policy: bool


@dataclass(frozen=True)
class AssistantOutcome:
    content: str
    retrieval_context_id: str | None
    metadata_json: dict[str, Any]
    thread_status: str
    active_rag_session_id: str | None


class ChatRunWorker:
    '''Perform short, lease-guarded database transitions for one chat run.'''

    def __init__(self, db: AsyncSession):
        self.db = db

    async def claim_run(
        self,
        run_id: UUID,
        worker_id: str,
    ) -> ClaimedChatRun | None:
        now = datetime.now(timezone.utc)

        async with self.db.begin():
            statement = (
                select(ChatRun)
                .where(
                    ChatRun.id == run_id,
                    ChatRun.status == 'queued',
                )
                .with_for_update(skip_locked=True)
            )
            result = await self.db.execute(statement)
            run = result.scalar_one_or_none()
            if run is None:
                return None

            run.status = 'running'
            run.attempt_count += 1
            run.lease_owner = worker_id
            run.lease_expires_at = now + RUN_LEASE_DURATION
            run.started_at = now

            request_payload = run.request_payload
            content = (
                request_payload.get('content')
                if isinstance(request_payload, dict)
                else None
            )
            rag_query = (
                request_payload.get('rag_query')
                if isinstance(request_payload, dict)
                else None
            )
            skip_followup_policy = bool(
                request_payload.get('skip_followup_policy', False)
                if isinstance(request_payload, dict)
                else False
            )
            claimed_run = ClaimedChatRun(
                id=run.id,
                operation=run.operation,
                input_rag_session_id=run.input_rag_session_id,
                content=content,
                rag_query=rag_query,
                skip_followup_policy=skip_followup_policy,
            )
            await self.db.flush()

        return claimed_run

    async def complete_run(
        self,
        run_id: UUID,
        worker_id: str,
        outcome: AssistantOutcome,
    ) -> bool:
        '''Persist an assistant message only while this invocation owns the lease.'''

        now = datetime.now(timezone.utc)
        async with self.db.begin():
            thread = await self._lock_run_thread(run_id)
            if thread is None:
                return False

            run = await self._lock_owned_running_run(run_id, worker_id)
            if run is None or run.thread_id != thread.id:
                return False

            assistant_message = ChatMessage(
                thread_id=thread.id,
                ordinal=thread.next_message_ordinal,
                role='assistant',
                content=outcome.content,
                retrieval_context_id=outcome.retrieval_context_id,
                metadata_json=outcome.metadata_json,
            )
            self.db.add(assistant_message)

            thread.next_message_ordinal += 1
            thread.status = outcome.thread_status
            thread.active_rag_session_id = outcome.active_rag_session_id

            run.status = 'completed'
            run.error_code = None
            run.error_message = None
            run.finished_at = now
            run.lease_owner = None
            run.lease_expires_at = None
            await self.db.flush()

        return True

    async def fail_run(
        self,
        run_id: UUID,
        worker_id: str,
        error_code: str,
        error_message: str,
    ) -> bool:
        '''Persist a safe failure without exposing upstream response content.'''

        now = datetime.now(timezone.utc)
        async with self.db.begin():
            thread = await self._lock_run_thread(run_id)
            if thread is None:
                return False

            run = await self._lock_owned_running_run(run_id, worker_id)
            if run is None or run.thread_id != thread.id:
                return False

            thread.status = 'failed'
            thread.active_rag_session_id = None

            run.status = 'failed'
            run.error_code = error_code
            run.error_message = error_message
            run.finished_at = now
            run.lease_owner = None
            run.lease_expires_at = None
            await self.db.flush()

        return True

    async def _lock_run_thread(self, run_id: UUID) -> ChatThread | None:
        '''Lock the parent thread before the run to match message creation order.'''

        thread_id_result = await self.db.execute(
            select(ChatRun.thread_id).where(ChatRun.id == run_id)
        )
        thread_id = thread_id_result.scalar_one_or_none()
        if thread_id is None:
            return None

        thread_result = await self.db.execute(
            select(ChatThread)
            .where(ChatThread.id == thread_id)
            .with_for_update()
        )
        return thread_result.scalar_one_or_none()

    async def _lock_owned_running_run(
        self,
        run_id: UUID,
        worker_id: str,
    ) -> ChatRun | None:
        result = await self.db.execute(
            select(ChatRun).where(ChatRun.id == run_id).with_for_update()
        )
        run = result.scalar_one_or_none()
        if (
            run is None
            or run.status != 'running'
            or run.lease_owner != worker_id
        ):
            return None
        return run


def map_rag_response(response: QueryResponse) -> AssistantOutcome:
    '''Map the validated RAG wire response into one durable assistant result.'''

    if response.answer.strip():
        return AssistantOutcome(
            content=response.answer,
            retrieval_context_id=(
                str(response.retrieval_context_id)
                if response.retrieval_context_id is not None
                else None
            ),
            metadata_json={
                'mitre_table': [
                    row.model_dump(mode='json')
                    for row in response.mitre_table
                ]
            },
            thread_status='idle',
            active_rag_session_id=None,
        )

    raise RagCallFailure(
        'rag_invalid_response',
        'RAG service returned an invalid response',
    )


async def resolve_followup_outcome(
    response: QueryResponse,
    *,
    original_user_content: str,
    skip_followup_policy: bool,
    source_run_id: UUID,
    policy: FollowUpPolicy | None = None,
) -> AssistantOutcome:
    """Apply at most one clarification and fail open to the RAG answer."""

    answer_outcome = map_rag_response(response)
    if skip_followup_policy or not settings.chat_followup_policy_enabled:
        return answer_outcome

    try:
        decision = await (policy or AnthropicFollowUpPolicy()).decide(
            user_content=original_user_content,
            rag_answer=response.answer,
        )
    except Exception as exc:
        logger.warning(
            "Chat follow-up policy failed open source_run_id=%s exception_type=%s",
            source_run_id,
            type(exc).__name__,
        )
        return answer_outcome

    if decision.action != "ask_followup":
        return answer_outcome
    return AssistantOutcome(
        content=decision.question,
        retrieval_context_id=None,
        metadata_json={
            "chat_followup": {
                "kind": "clarification",
                "source_run_id": str(source_run_id),
            }
        },
        thread_status="awaiting_followup",
        active_rag_session_id=None,
    )


async def process_chat_run(run_id: UUID) -> None:
    '''Process one run in-process; queued work is lost if this process exits.'''

    worker_id = f'chat-run:{uuid4()}'
    async with async_session() as claim_db:
        claimed_run = await ChatRunWorker(claim_db).claim_run(run_id, worker_id)

    if claimed_run is None:
        return

    try:
        if not isinstance(claimed_run.content, str):
            raise ValueError('Chat run request content is not a string')
        if not isinstance(claimed_run.rag_query, str):
            raise ValueError('Chat run RAG query is not a string')
        if claimed_run.operation != 'query':
            raise ValueError('Chat run operation is invalid')

        response = await request_rag(claimed_run.rag_query)
        outcome = await resolve_followup_outcome(
            response,
            original_user_content=claimed_run.content,
            skip_followup_policy=claimed_run.skip_followup_policy,
            source_run_id=claimed_run.id,
        )

        async with async_session() as finalize_db:
            await ChatRunWorker(finalize_db).complete_run(
                run_id,
                worker_id,
                outcome,
            )
    except RagCallFailure as exc:
        await _record_failure(run_id, worker_id, exc.code, exc.message)
    except Exception:
        await _record_failure(
            run_id,
            worker_id,
            'rag_processing_error',
            'Failed to process chat message',
        )


async def _record_failure(
    run_id: UUID,
    worker_id: str,
    error_code: str,
    error_message: str,
) -> None:
    async with async_session() as failure_db:
        await ChatRunWorker(failure_db).fail_run(
            run_id,
            worker_id,
            error_code,
            error_message,
        )
