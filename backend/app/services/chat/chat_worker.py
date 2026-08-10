'''Claim, execute, and finalize persistent background chat runs.'''

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.config import settings
from app.models.chat import ChatMessage, ChatRun, ChatThread
from app.schemas.chat.rag import QueryResponse
from app.services.chat.chat_message import reconstruct_clarification_chain
from app.services.extraction.demo_extraction import add_demo_chat_extraction
from app.services.llm.core_llm import resolve_core_llm_target
from app.services.chat.followup_policy import (
    AnthropicFollowUpPolicy,
    ClarificationExchange,
    FOLLOWUP_POLICY_VERSION,
    FOLLOWUP_PROMPT_VERSION,
    FollowUpDecision,
    FollowUpPolicy,
    FollowUpPolicyResult,
    build_clarified_query,
)
from app.services.extraction.llm_extraction import (
    BASELINE_EXTRACTION_MODE,
    BASELINE_EXTRACTION_PROMPT_VERSION,
    BASELINE_EXTRACTION_VERSION,
    EXTRACTION_METADATA_KEY,
    ExtractionInput,
    ExtractionModelAdapter,
    ExtractionSourceMessage,
    build_extraction_input,
    run_baseline_extraction,
)
from app.services.chat.rag_client import RagCallFailure, request_rag

logger = logging.getLogger("app.chat")
RUN_LEASE_DURATION = timedelta(minutes=6)


@dataclass(frozen=True)
class ClaimedChatRun:
    """Detached input needed after the claim transaction has closed."""

    id: UUID
    operation: str
    input_rag_session_id: str | None
    content: object
    rag_query: object
    original_user_content: object
    clarification_exchanges: tuple[ClarificationExchange, ...]
    followup_root_ordinal: int
    extraction_input: ExtractionInput | None = None

@dataclass(frozen=True)
class AssistantOutcome:
    content: str
    retrieval_context_id: str | None
    metadata_json: dict[str, Any]
    thread_status: str
    active_rag_session_id: str | None


@dataclass(frozen=True)
class FollowUpResolution:
    """The gate result and the audit record carried into the final message."""

    outcome: AssistantOutcome | None
    metadata_json: dict[str, Any]


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
            history: list[ChatMessage] | None = None
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
                if request_index is None:
                    thread_result = await self.db.execute(
                        select(ChatThread)
                        .where(ChatThread.id == run.thread_id)
                        .with_for_update()
                    )
                    thread = thread_result.scalar_one_or_none()
                    if thread is not None:
                        thread.status = (
                            "awaiting_followup"
                            if isinstance(requested_round, int)
                            and not isinstance(requested_round, bool)
                            and requested_round > 0
                            else "failed"
                        )
                        thread.active_rag_session_id = None
                    run.status = "failed"
                    run.error_code = "chat_followup_request_missing"
                    run.error_message = (
                        "The persisted chat request could not be reconstructed."
                    )
                    run.finished_at = now
                    run.lease_owner = None
                    run.lease_expires_at = None
                    await self.db.flush()
                    return None
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

            extraction_input: ExtractionInput | None = None
            try:
                if history is not None:
                    extraction_input = build_extraction_input(
                        thread_id=run.thread_id,
                        messages=history,
                        root_ordinal=followup_root_ordinal,
                    )
                elif isinstance(content, str):
                    extraction_input = ExtractionInput(
                        thread_id=run.thread_id,
                        messages=[
                            ExtractionSourceMessage(
                                message_id=run.request_message_id,
                                ordinal=followup_root_ordinal,
                                source_type="user_case_statement",
                                content=content,
                            )
                        ],
                    )
            except (TypeError, ValueError):
                logger.warning(
                    "Chat extraction source packet could not be built "
                    "run_id=%s",
                    run.id,
                )

            claimed_run = ClaimedChatRun(
                id=run.id,
                operation=run.operation,
                input_rag_session_id=run.input_rag_session_id,
                content=content,
                rag_query=rag_query,
                original_user_content=original_user_content,
                clarification_exchanges=clarification_exchanges,
                followup_root_ordinal=followup_root_ordinal,
                extraction_input=extraction_input,
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
        followup_metadata_json: dict[str, Any] | None = None,
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
            if followup_metadata_json:
                updated_payload = dict(request_payload or {})
                followup_trace = followup_metadata_json.get("chat_followup")
                if isinstance(followup_trace, dict):
                    updated_payload["chat_followup"] = followup_trace
                    run.request_payload = updated_payload
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


async def evaluate_followup_outcome(
    *,
    original_user_content: str,
    clarification_exchanges: Sequence[ClarificationExchange],
    followup_root_ordinal: int,
    source_run_id: UUID,
    policy: FollowUpPolicy | None = None,
) -> FollowUpResolution:
    """Run the generic pre-RAG gate and return an auditable resolution."""

    round_number = len(clarification_exchanges) + 1
    prior_exchange_count = len(clarification_exchanges)

    if not settings.chat_followup_policy_enabled:
        return FollowUpResolution(
            outcome=None,
            metadata_json=_followup_metadata(
                source_run_id=source_run_id,
                followup_root_ordinal=followup_root_ordinal,
                round_number=round_number,
                prior_exchange_count=prior_exchange_count,
                action="proceed",
                question="",
                reason_code="followup_policy_disabled",
                stop_reason="policy_disabled",
            ),
        )
    if len(clarification_exchanges) >= settings.chat_followup_max_rounds:
        return FollowUpResolution(
            outcome=None,
            metadata_json=_followup_metadata(
                source_run_id=source_run_id,
                followup_root_ordinal=followup_root_ordinal,
                round_number=round_number,
                prior_exchange_count=prior_exchange_count,
                action="proceed",
                question="",
                reason_code="max_rounds_reached",
                stop_reason="max_rounds_reached",
            ),
        )
    if clarification_exchanges and _answer_indicates_unavailable(
        clarification_exchanges[-1].answer
    ):
        return FollowUpResolution(
            outcome=None,
            metadata_json=_followup_metadata(
                source_run_id=source_run_id,
                followup_root_ordinal=followup_root_ordinal,
                round_number=round_number,
                prior_exchange_count=prior_exchange_count,
                action="proceed",
                question="",
                reason_code="answer_unavailable",
                stop_reason="answer_unavailable",
            ),
        )

    started = time.perf_counter()
    try:
        active_policy = policy or AnthropicFollowUpPolicy()
        decide_with_metadata = getattr(active_policy, "decide_with_metadata", None)
        if callable(decide_with_metadata):
            raw_result = await decide_with_metadata(
                original_user_content=original_user_content,
                clarification_exchanges=clarification_exchanges,
            )
        else:
            raw_result = await active_policy.decide(
                original_user_content=original_user_content,
                clarification_exchanges=clarification_exchanges,
            )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        result = _coerce_policy_result(raw_result, elapsed_ms=elapsed_ms)
        decision = result.decision
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        failure_code = _followup_failure_code(exc)
        logger.warning(
            "Chat follow-up policy failed open source_run_id=%s failure_code=%s",
            source_run_id,
            failure_code,
        )
        return FollowUpResolution(
            outcome=None,
            metadata_json=_followup_metadata(
                source_run_id=source_run_id,
                followup_root_ordinal=followup_root_ordinal,
                round_number=round_number,
                prior_exchange_count=prior_exchange_count,
                action="proceed",
                question="",
                reason_code="policy_failed_open",
                stop_reason="policy_failed_open",
                latency_ms=elapsed_ms,
                failure_code=failure_code,
            ),
        )

    if decision.action == "proceed":
        return FollowUpResolution(
            outcome=None,
            metadata_json=_followup_metadata(
                source_run_id=source_run_id,
                followup_root_ordinal=followup_root_ordinal,
                round_number=round_number,
                prior_exchange_count=prior_exchange_count,
                action=decision.action,
                question=decision.question,
                reason_code=decision.reason_code,
                stop_reason="policy_proceed",
                latency_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                provider=result.provider,
                model=result.model,
            ),
        )

    normalized_question = _normalized_question(decision.question)
    if any(
        _normalized_question(exchange.question) == normalized_question
        for exchange in clarification_exchanges
    ):
        return FollowUpResolution(
            outcome=None,
            metadata_json=_followup_metadata(
                source_run_id=source_run_id,
                followup_root_ordinal=followup_root_ordinal,
                round_number=round_number,
                prior_exchange_count=prior_exchange_count,
                action="proceed",
                question="",
                reason_code="duplicate_question",
                stop_reason="duplicate_question",
                latency_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                provider=result.provider,
                model=result.model,
            ),
        )
    return FollowUpResolution(
        outcome=AssistantOutcome(
            content=decision.question,
            retrieval_context_id=None,
            metadata_json=_followup_metadata(
                source_run_id=source_run_id,
                followup_root_ordinal=followup_root_ordinal,
                round_number=round_number,
                prior_exchange_count=prior_exchange_count,
                action=decision.action,
                question=decision.question,
                reason_code=decision.reason_code,
                stop_reason="ask_followup",
                latency_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                provider=result.provider,
                model=result.model,
                rag_skipped=True,
            ),
            thread_status="awaiting_followup",
            active_rag_session_id=None,
        ),
        metadata_json={},
    )


async def resolve_followup_outcome(
    *,
    original_user_content: str,
    clarification_exchanges: Sequence[ClarificationExchange],
    followup_root_ordinal: int,
    source_run_id: UUID,
    policy: FollowUpPolicy | None = None,
) -> AssistantOutcome | None:
    """Compatibility wrapper returning only the pending assistant outcome."""

    resolution = await evaluate_followup_outcome(
        original_user_content=original_user_content,
        clarification_exchanges=clarification_exchanges,
        followup_root_ordinal=followup_root_ordinal,
        source_run_id=source_run_id,
        policy=policy,
    )
    return resolution.outcome


def _coerce_policy_result(
    raw_result: object,
    *,
    elapsed_ms: float,
) -> FollowUpPolicyResult:
    if isinstance(raw_result, FollowUpPolicyResult):
        return FollowUpPolicyResult(
            decision=FollowUpDecision.model_validate(raw_result.decision),
            latency_ms=(
                raw_result.latency_ms
                if raw_result.latency_ms is not None
                else elapsed_ms
            ),
            input_tokens=_safe_token_count(raw_result.input_tokens),
            output_tokens=_safe_token_count(raw_result.output_tokens),
            provider=raw_result.provider,
            model=raw_result.model,
        )
    return FollowUpPolicyResult(
        decision=FollowUpDecision.model_validate(raw_result),
        latency_ms=elapsed_ms,
    )


def _safe_token_count(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _followup_failure_code(error: Exception) -> str:
    if isinstance(error, (asyncio.TimeoutError, httpx.TimeoutException)):
        return "policy_timeout"
    if isinstance(error, (json.JSONDecodeError, ValueError, TypeError)):
        return "policy_invalid_output"
    return "policy_error"


def _followup_metadata(
    *,
    source_run_id: UUID,
    followup_root_ordinal: int,
    round_number: int,
    prior_exchange_count: int,
    action: str,
    question: str,
    reason_code: str,
    stop_reason: str,
    latency_ms: float | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    provider: str | None = None,
    model: str | None = None,
    failure_code: str | None = None,
    rag_skipped: bool = True,
    rag_invoked: bool = False,
) -> dict[str, Any]:
    target = resolve_core_llm_target(
        settings.chat_followup_policy_model,
        require_key=False,
    )
    return {
        "chat_followup": {
            "kind": "clarification" if action == "ask_followup" else "decision",
            "policy_version": FOLLOWUP_POLICY_VERSION,
            "prompt_version": FOLLOWUP_PROMPT_VERSION,
            "provider": provider or target.provider,
            "model": model or target.model,
            "action": action,
            "question": question,
            "reason_code": reason_code,
            "source_run_id": str(source_run_id),
            "root_ordinal": followup_root_ordinal,
            "round": round_number,
            "prior_exchange_count": prior_exchange_count,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "failure_code": failure_code,
            "stop_reason": stop_reason,
            "rag_skipped": rag_skipped,
            "rag_invoked": rag_invoked,
        }
    }


def _mark_followup_rag_invoked(
    outcome: AssistantOutcome,
    metadata_json: dict[str, Any],
) -> AssistantOutcome:
    merged_metadata = _mark_followup_rag_invoked_metadata(metadata_json)
    if not merged_metadata:
        return outcome
    output_metadata = dict(outcome.metadata_json)
    output_metadata["chat_followup"] = merged_metadata["chat_followup"]
    return replace(outcome, metadata_json=output_metadata)


def _mark_followup_rag_invoked_metadata(
    metadata_json: dict[str, Any],
) -> dict[str, Any]:
    trace = metadata_json.get("chat_followup")
    if not isinstance(trace, dict):
        return {}
    return {
        **metadata_json,
        "chat_followup": {
            **trace,
            "rag_skipped": False,
            "rag_invoked": True,
        },
    }


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
    "ไม่ทราบ",
    "ไม่รู้",
    "ไม่มีข้อมูล",
    "ไม่สามารถระบุได้",
    "ไม่สามารถยืนยันได้",
    "หาไม่ได้",
    "ไม่พร้อมใช้งาน",
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
    for phrase in _UNAVAILABLE_ANSWER_PHRASES:
        if any(ord(character) > 127 for character in phrase):
            if phrase in normalized:
                return True
        elif re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", normalized):
            return True
    return False


async def process_chat_run(
    run_id: UUID,
    *,
    policy: FollowUpPolicy | None = None,
    rag_call: Callable[[str], Awaitable[QueryResponse]] | None = None,
    extraction_adapter: ExtractionModelAdapter | None = None,
) -> None:
    '''Process one run in-process; queued work is lost if this process exits.'''

    worker_id = f'chat-run:{uuid4()}'
    async with async_session() as claim_db:
        claimed_run = await ChatRunWorker(claim_db).claim_run(run_id, worker_id)

    if claimed_run is None:
        return

    followup_metadata_json: dict[str, Any] | None = None
    try:
        if not isinstance(claimed_run.content, str):
            raise ValueError('Chat run request content is not a string')
        if not isinstance(claimed_run.rag_query, str):
            raise ValueError('Chat run RAG query is not a string')
        if not isinstance(claimed_run.original_user_content, str):
            raise ValueError('Chat follow-up root content is not a string')
        if claimed_run.operation != 'query':
            raise ValueError('Chat run operation is invalid')

        followup_resolution = await evaluate_followup_outcome(
            original_user_content=claimed_run.original_user_content,
            clarification_exchanges=claimed_run.clarification_exchanges,
            followup_root_ordinal=claimed_run.followup_root_ordinal,
            source_run_id=claimed_run.id,
            policy=policy,
        )
        followup_metadata_json = _mark_followup_rag_invoked_metadata(
            followup_resolution.metadata_json
        )
        if followup_resolution.outcome is not None:
            async with async_session() as finalize_db:
                await ChatRunWorker(finalize_db).complete_run(
                    run_id,
                    worker_id,
                    followup_resolution.outcome,
                )
            return

        rag_query = claimed_run.rag_query
        if claimed_run.clarification_exchanges:
            rag_query = build_clarified_query(
                original_user_content=claimed_run.original_user_content,
                clarification_exchanges=claimed_run.clarification_exchanges,
            )
        response = await (rag_call or request_rag)(rag_query)
        outcome = map_rag_response(response)
        outcome = _mark_followup_rag_invoked(
            outcome,
            followup_metadata_json or {},
        )
        outcome = await attach_llm_extraction(
            outcome,
            claimed_run,
            adapter=extraction_adapter,
        )

        async with async_session() as finalize_db:
            await ChatRunWorker(finalize_db).complete_run(
                run_id,
                worker_id,
                outcome,
            )
    except RagCallFailure as exc:
        await _record_failure(
            run_id,
            worker_id,
            exc.code,
            exc.message,
            followup_metadata_json=followup_metadata_json,
        )
    except Exception:
        await _record_failure(
            run_id,
            worker_id,
            'rag_processing_error',
            'Failed to process chat message',
            followup_metadata_json=followup_metadata_json,
        )


async def _record_failure(
    run_id: UUID,
    worker_id: str,
    error_code: str,
    error_message: str,
    followup_metadata_json: dict[str, Any] | None = None,
) -> None:
    async with async_session() as failure_db:
        await ChatRunWorker(failure_db).fail_run(
            run_id,
            worker_id,
            error_code,
            error_message,
            followup_metadata_json=followup_metadata_json,
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


async def attach_llm_extraction(
    outcome: AssistantOutcome,
    claimed_run: ClaimedChatRun,
    *,
    adapter: ExtractionModelAdapter | None = None,
) -> AssistantOutcome:
    """Attach a success or explicit failure record after a terminal answer."""

    if (
        outcome.thread_status != "idle"
        or claimed_run.extraction_input is None
    ):
        return outcome

    extraction_input = claimed_run.extraction_input
    try:
        result = await run_baseline_extraction(
            extraction_input,
            adapter=adapter,
        )
        extraction_metadata = result.metadata(extraction_input)
    except Exception:
        # A valid RAG answer must never be lost because the optional baseline
        # extractor failed outside its normal typed failure paths.
        logger.exception(
            "Chat extraction failed outside typed failure handling run_id=%s",
            claimed_run.id,
        )
        target = resolve_core_llm_target(
            settings.chat_extraction_model,
            require_key=False,
        )
        extraction_metadata = {
            "version": BASELINE_EXTRACTION_VERSION,
            "mode": BASELINE_EXTRACTION_MODE,
            "status": "failed",
            "prompt_version": BASELINE_EXTRACTION_PROMPT_VERSION,
            "provider": target.provider,
            "model": target.model,
            "validation_status": "failed",
            "latency_ms": 0.0,
            "input_tokens": None,
            "output_tokens": None,
            "source_message_ids": [
                str(message.message_id) for message in extraction_input.messages
            ],
            "raw_response": None,
            "failure_code": "extraction_internal_error",
            "failure_message": "The extraction failed before validation",
        }

    metadata = dict(outcome.metadata_json)
    metadata[EXTRACTION_METADATA_KEY] = extraction_metadata
    return replace(outcome, metadata_json=metadata)
