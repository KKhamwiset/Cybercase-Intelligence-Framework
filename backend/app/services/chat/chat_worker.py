'''Claim, execute, and finalize persistent background chat runs.'''

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.config import settings
from app.models.chat import ChatMessage, ChatRun, ChatThread
from app.schemas.chat.rag import QueryResponse
from app.services.chat.chat_message import reconstruct_clarification_chain
from app.services.chat.demo_extraction import add_demo_chat_extraction
from app.services.chat.followup_policy import (
    AnthropicFollowUpPolicy,
    ClarificationExchange,
    FollowUpDecision,
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
    original_user_content: object
    clarification_exchanges: tuple[ClarificationExchange, ...]
    followup_root_ordinal: int


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
                request_payload.get('rag_query', content)
                if isinstance(request_payload, dict)
                else None
            )
            requested_root_ordinal = (
                request_payload.get('followup_root_ordinal')
                if isinstance(request_payload, dict)
                else None
            )
            if (
                not isinstance(requested_root_ordinal, int)
                or isinstance(requested_root_ordinal, bool)
                or requested_root_ordinal < 1
            ):
                requested_root_ordinal = None
            requested_round = (
                request_payload.get('followup_round')
                if isinstance(request_payload, dict)
                else None
            )
            if (
                not isinstance(requested_round, int)
                or isinstance(requested_round, bool)
                or requested_round < 0
            ):
                requested_round = None
            legacy_followup = (
                request_payload.get('skip_followup_policy') is True
                if isinstance(request_payload, dict)
                else False
            )

            original_user_content: object = content
            clarification_exchanges: tuple[
                ClarificationExchange, ...
            ] = ()
            followup_root_ordinal = requested_root_ordinal
            if requested_root_ordinal is not None and requested_round == 0:
                pass
            elif requested_root_ordinal is None and not legacy_followup:
                request_message_result = await self.db.execute(
                    select(ChatMessage).where(
                        ChatMessage.id == run.request_message_id
                    )
                )
                request_message = request_message_result.scalar_one_or_none()
                if request_message is not None:
                    original_user_content = request_message.content
                    followup_root_ordinal = request_message.ordinal
            else:
                history_result = await self.db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.thread_id == run.thread_id)
                    .order_by(ChatMessage.ordinal)
                )
                history = history_result.scalars().all()
                request_index = next(
                    (
                        index
                        for index, message in enumerate(history)
                        if message.id == run.request_message_id
                    ),
                    None,
                )
                if request_index is not None:
                    history = history[: request_index + 1]
                chain = reconstruct_clarification_chain(
                    history,
                    root_ordinal=requested_root_ordinal,
                )
                if chain is not None:
                    original_user_content = chain.original_user_content
                    clarification_exchanges = chain.exchanges
                    followup_root_ordinal = chain.root_ordinal
                if followup_root_ordinal is None:
                    request_message = next(
                        (
                            message
                            for message in history
                            if message.id == run.request_message_id
                        ),
                        None,
                    )
                    if request_message is not None:
                        original_user_content = request_message.content
                        followup_root_ordinal = request_message.ordinal
            if followup_root_ordinal is None:
                followup_root_ordinal = 1

            claimed_run = ClaimedChatRun(
                id=run.id,
                operation=run.operation,
                input_rag_session_id=run.input_rag_session_id,
                content=content,
                rag_query=rag_query,
                original_user_content=original_user_content,
                clarification_exchanges=clarification_exchanges,
                followup_root_ordinal=followup_root_ordinal,
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

            request_payload = run.request_payload
            followup_round = (
                request_payload.get('followup_round')
                if isinstance(request_payload, dict)
                else None
            )
            thread.status = (
                'awaiting_followup'
                if isinstance(followup_round, int)
                and not isinstance(followup_round, bool)
                and followup_round > 0
                else 'failed'
            )
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
    clarification_exchanges: Sequence[ClarificationExchange],
    followup_root_ordinal: int,
    source_run_id: UUID,
    policy: FollowUpPolicy | None = None,
) -> AssistantOutcome:
    """Reevaluate accumulated clarification context and fail open on errors."""

    answer_outcome = map_rag_response(response)
    if not settings.chat_followup_policy_enabled:
        return answer_outcome
    if len(clarification_exchanges) >= settings.chat_followup_max_rounds:
        return answer_outcome
    if clarification_exchanges and _answer_indicates_unavailable(
        clarification_exchanges[-1].answer
    ):
        return answer_outcome

    try:
        raw_decision = await (policy or AnthropicFollowUpPolicy()).decide(
            original_user_content=original_user_content,
            clarification_exchanges=clarification_exchanges,
            rag_answer=response.answer,
        )
        decision = FollowUpDecision.model_validate(raw_decision)
    except Exception as exc:
        logger.warning(
            "Chat follow-up policy failed open source_run_id=%s exception_type=%s",
            source_run_id,
            type(exc).__name__,
        )
        return answer_outcome

    if decision.action != "ask_followup":
        return answer_outcome
    normalized_question = _normalized_question(decision.question)
    if any(
        _normalized_question(exchange.question) == normalized_question
        for exchange in clarification_exchanges
    ):
        return answer_outcome
    return AssistantOutcome(
        content=decision.question,
        retrieval_context_id=None,
        metadata_json={
            "chat_followup": {
                "kind": "clarification",
                "source_run_id": str(source_run_id),
                "root_ordinal": followup_root_ordinal,
                "round": len(clarification_exchanges) + 1,
            }
        },
        thread_status="awaiting_followup",
        active_rag_session_id=None,
    )


def _normalized_question(question: str) -> str:
    normalized = unicodedata.normalize("NFKC", question)
    normalized = " ".join(normalized.split()).casefold()
    while normalized and unicodedata.category(normalized[-1]).startswith("P"):
        normalized = normalized[:-1].rstrip()
    return normalized


_UNAVAILABLE_ANSWER_PHRASES = (
    "unknown",
    "unavailable",
    "not available",
    "not provided",
    "not known",
    "no information",
    "cannot be obtained",
    "can't be obtained",
    "could not be obtained",
    "couldn't be obtained",
    "cannot be determined",
    "can't be determined",
    "could not be determined",
    "couldn't be determined",
    "i don't know",
    "i do not know",
    "we don't know",
    "we do not know",
    "absent",
    "missing",
    "n/a",
)


def _answer_indicates_unavailable(answer: str) -> bool:
    normalized = unicodedata.normalize("NFKC", answer)
    normalized = " ".join(normalized.split()).casefold()
    if not normalized:
        return False
    normalized = normalized.strip(" .,!?:;()[]{}")
    if normalized in {"none", "not known", "not available", "unavailable"}:
        return True
    if re.search(r"\bnot\s+unavailable\b", normalized):
        return False
    return any(
        re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", normalized)
        for phrase in _UNAVAILABLE_ANSWER_PHRASES
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
        if not isinstance(claimed_run.original_user_content, str):
            raise ValueError('Chat follow-up root content is not a string')
        if claimed_run.operation != 'query':
            raise ValueError('Chat run operation is invalid')

        response = await request_rag(claimed_run.rag_query)
        outcome = await resolve_followup_outcome(
            response,
            original_user_content=claimed_run.original_user_content,
            clarification_exchanges=claimed_run.clarification_exchanges,
            followup_root_ordinal=claimed_run.followup_root_ordinal,
            source_run_id=claimed_run.id,
        )
        outcome = attach_demo_extraction(outcome, claimed_run)

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


def attach_demo_extraction(
    outcome: AssistantOutcome,
    claimed_run: ClaimedChatRun,
) -> AssistantOutcome:
    """Attach demo candidates only to terminal assistant answers."""

    if outcome.thread_status != "idle":
        return outcome

    source_text = "\n".join(
        [
            str(claimed_run.original_user_content),
            *(exchange.answer for exchange in claimed_run.clarification_exchanges),
        ]
    )
    return replace(
        outcome,
        metadata_json=add_demo_chat_extraction(
            outcome.metadata_json,
            source_text,
        ),
    )
