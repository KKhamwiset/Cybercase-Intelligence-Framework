'''Claim, execute, and finalize persistent background chat runs.'''

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.case_state import CaseStateVersion
from app.models.chat import ChatMessage, ChatRun, ChatThread
from app.models.rag_context import RagContext
from app.schemas.chat.rag import QueryResponse
from app.services.case_analysis import (
    CaseAnalysisFailure,
    request_case_analysis,
)
from app.services.chat.chat_message import reconstruct_clarification_chain
from app.services.chat.clarification_gate import (
    FollowUpResolution,
    _answer_indicates_unavailable,
    _coerce_policy_result,
    _followup_failure_code,
    _followup_metadata,
    _mark_followup_rag_invoked,
    _mark_followup_rag_invoked_metadata,
    _normalized_question,
    _safe_token_count,
    evaluate_followup_outcome,
    resolve_followup_outcome,
)
from app.services.chat.extraction_stage import (
    ExtractionStageFailure,
    attach_llm_extraction,
    run_validated_case_state_extraction,
)
from app.services.chat.followup_policy import (
    ClarificationExchange,
    FollowUpPolicy,
    build_clarified_query,
)
from app.services.chat.outcome_mapper import (
    AssistantOutcome,
    RagContextPayload,
    _validated_rag_context_payload,
    map_case_analysis_response,
    map_initial_case_analysis_response,
    map_rag_response,
)
from app.services.chat.rag_client import RagCallFailure, request_rag
from app.services.extraction.llm_extraction import (
    EXTRACTION_METADATA_KEY,
    ExtractionInput,
    ExtractionModelAdapter,
    ExtractionSourceMessage,
    build_extraction_input,
)

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
    post_answer_action: str | None = None
    case_state_json: dict[str, object] | None = None
    analysis_context: dict[str, object] | None = None


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
            post_answer_action = (
                request_payload.get('action')
                if isinstance(request_payload, dict)
                else None
            )
            if post_answer_action not in (None, 'ask', 'add_case_info'):
                post_answer_action = None

            case_state_json: dict[str, object] | None = None
            analysis_context: dict[str, object] | None = None
            if post_answer_action == 'ask':
                pointer_result = await self.db.execute(
                    select(ChatThread.current_case_state_version_id).where(
                        ChatThread.id == run.thread_id,
                    )
                )
                current_state_version_id = pointer_result.scalar_one_or_none()
                if current_state_version_id is not None:
                    state_result = await self.db.execute(
                        select(CaseStateVersion).where(
                            CaseStateVersion.id == current_state_version_id,
                            CaseStateVersion.thread_id == run.thread_id,
                        )
                    )
                    case_state = state_result.scalar_one_or_none()
                    if case_state is not None and isinstance(
                        case_state.state_json,
                        dict,
                    ):
                        case_state_json = deepcopy(case_state.state_json)
                        rag_context_result = await self.db.execute(
                            select(RagContext).where(
                                RagContext.thread_id == run.thread_id,
                                RagContext.case_state_version_id
                                == current_state_version_id,
                            )
                        )
                        rag_context = rag_context_result.scalar_one_or_none()
                        if rag_context is not None:
                            mitre_table = rag_context.mitre_table
                            analysis_context = {
                                'retrieved_context': (
                                    rag_context.context
                                    if isinstance(rag_context.context, str)
                                    else ''
                                ),
                                'retrieval_context_id': rag_context.retrieval_context_id,
                                'mitre_table': (
                                    deepcopy(mitre_table)
                                    if isinstance(mitre_table, list)
                                    else []
                                ),
                                'previous_analysis': None,
                            }

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
            if post_answer_action is None:
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
                post_answer_action=post_answer_action,
                case_state_json=case_state_json,
                analysis_context=analysis_context,
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

            has_case_state = outcome.validated_case_state_json is not None
            has_rag_context = outcome.rag_context_payload is not None
            if has_case_state != has_rag_context:
                raise ValueError(
                    "A successful initial analysis must persist Case State and "
                    "durable RAG context together"
                )

            case_state_version: CaseStateVersion | None = None
            if (
                outcome.validated_case_state_json is not None
                and thread.current_case_state_version_id is None
            ):
                case_state_version = CaseStateVersion(
                    id=uuid4(),
                    thread_id=thread.id,
                    version=1,
                    parent_version_id=None,
                    trigger_message_id=run.request_message_id,
                    delta_json={},
                    state_json=outcome.validated_case_state_json,
                )
                self.db.add(case_state_version)
                await self.db.flush()
                thread.current_case_state_version_id = case_state_version.id

            if outcome.rag_context_payload is not None:
                if case_state_version is None:
                    raise ValueError(
                        "A durable RAG context requires a new case-state version"
                    )
                payload = outcome.rag_context_payload
                self.db.add(
                    RagContext(
                        retrieval_context_id=payload.retrieval_context_id,
                        thread_id=thread.id,
                        case_state_version_id=case_state_version.id,
                        context=payload.context,
                        mitre_table=deepcopy(list(payload.mitre_table)),
                    )
                )

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
                for audit_key in ("chat_followup", EXTRACTION_METADATA_KEY):
                    audit_value = followup_metadata_json.get(audit_key)
                    if isinstance(audit_value, dict):
                        updated_payload[audit_key] = audit_value
                if updated_payload != dict(request_payload or {}):
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


async def process_chat_run(
    run_id: UUID,
    *,
    policy: FollowUpPolicy | None = None,
    rag_call: Callable[[str], Awaitable[QueryResponse]] | None = None,
    ask_call: Callable[..., Awaitable[str]] | None = None,
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

        if claimed_run.post_answer_action == 'add_case_info':
            outcome = AssistantOutcome(
                content=(
                    'Case-information update routing is not implemented yet. '
                    'No case state was changed.'
                ),
                retrieval_context_id=None,
                metadata_json={
                    'chat_action': {
                        'action': 'add_case_info',
                        'route': 'case_update',
                        'state_mutated': False,
                        'status': 'not_implemented',
                    }
                },
                thread_status='answered',
                active_rag_session_id=None,
            )
            async with async_session() as finalize_db:
                await ChatRunWorker(finalize_db).complete_run(
                    run_id,
                    worker_id,
                    outcome,
                )
            return

        if claimed_run.post_answer_action == 'ask':
            if not isinstance(claimed_run.case_state_json, dict):
                raise CaseAnalysisFailure(
                    'analysis_context_missing',
                    'The current case state could not be loaded for ASK',
                )
            if not isinstance(claimed_run.analysis_context, dict):
                raise CaseAnalysisFailure(
                    'analysis_context_missing',
                    'The latest completed analysis could not be loaded for ASK',
                )
            answer = await (ask_call or request_case_analysis)(
                case_state_json=claimed_run.case_state_json,
                analysis_context=claimed_run.analysis_context,
                question=claimed_run.content,
            )
            if not isinstance(answer, str) or not answer.strip():
                raise CaseAnalysisFailure(
                    'analysis_invalid_response',
                    'The post-answer analysis returned no answer',
                )
            outcome = map_case_analysis_response(
                answer.strip(),
                analysis_context=claimed_run.analysis_context,
            )
            async with async_session() as finalize_db:
                await ChatRunWorker(finalize_db).complete_run(
                    run_id,
                    worker_id,
                    outcome,
                )
            return

        followup_resolution = await evaluate_followup_outcome(
            original_user_content=claimed_run.original_user_content,
            clarification_exchanges=claimed_run.clarification_exchanges,
            followup_root_ordinal=claimed_run.followup_root_ordinal,
            source_run_id=claimed_run.id,
            policy=policy,
        )
        followup_metadata_json = followup_resolution.metadata_json
        if followup_resolution.outcome is not None:
            async with async_session() as finalize_db:
                await ChatRunWorker(finalize_db).complete_run(
                    run_id,
                    worker_id,
                    followup_resolution.outcome,
                )
            return

        validated_case_state_json, extraction_metadata = (
            await run_validated_case_state_extraction(
                claimed_run,
                adapter=extraction_adapter,
            )
        )
        followup_metadata_json = {
            **(followup_metadata_json or {}),
            EXTRACTION_METADATA_KEY: extraction_metadata,
        }
        if validated_case_state_json is None:
            failure_code = extraction_metadata.get(
                'failure_code',
                'extraction_failed',
            )
            failure_message = extraction_metadata.get(
                'failure_message',
                'The extraction did not produce a validated Case State',
            )
            raise ExtractionStageFailure(
                str(failure_code),
                str(failure_message),
                followup_metadata_json,
            )

        rag_query = claimed_run.rag_query
        if claimed_run.clarification_exchanges:
            rag_query = build_clarified_query(
                original_user_content=claimed_run.original_user_content,
                clarification_exchanges=claimed_run.clarification_exchanges,
            )
        followup_metadata_json = {
            **_mark_followup_rag_invoked_metadata(
                followup_resolution.metadata_json
            ),
            EXTRACTION_METADATA_KEY: extraction_metadata,
        }
        response = await (rag_call or request_rag)(rag_query)
        rag_context_payload = _validated_rag_context_payload(response)
        analysis_context = rag_context_payload.to_analysis_context()
        answer = await (ask_call or request_case_analysis)(
            case_state_json=validated_case_state_json,
            analysis_context=analysis_context,
            question=None,
        )
        if not isinstance(answer, str) or not answer.strip():
            raise CaseAnalysisFailure(
                'analysis_invalid_response',
                'The initial Main Case Analysis returned no answer',
            )
        outcome = map_initial_case_analysis_response(
            answer.strip(),
            rag_context_payload=rag_context_payload,
            validated_case_state_json=validated_case_state_json,
            extraction_metadata=extraction_metadata,
            followup_metadata_json=followup_metadata_json or {},
        )

        async with async_session() as finalize_db:
            await ChatRunWorker(finalize_db).complete_run(
                run_id,
                worker_id,
                outcome,
            )
    except ExtractionStageFailure as exc:
        await _record_failure(
            run_id,
            worker_id,
            exc.code,
            exc.message,
            followup_metadata_json=exc.metadata_json,
        )
    except RagCallFailure as exc:
        await _record_failure(
            run_id,
            worker_id,
            exc.code,
            exc.message,
            followup_metadata_json=followup_metadata_json,
        )
    except CaseAnalysisFailure as exc:
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


__all__ = [
    "ClaimedChatRun",
    "ChatRunWorker",
    "process_chat_run",
    "RagContextPayload",
    "AssistantOutcome",
    "map_rag_response",
    "_validated_rag_context_payload",
    "map_initial_case_analysis_response",
    "map_case_analysis_response",
    "FollowUpResolution",
    "evaluate_followup_outcome",
    "resolve_followup_outcome",
    "_coerce_policy_result",
    "_safe_token_count",
    "_followup_failure_code",
    "_followup_metadata",
    "_mark_followup_rag_invoked",
    "_mark_followup_rag_invoked_metadata",
    "_normalized_question",
    "_answer_indicates_unavailable",
    "ExtractionStageFailure",
    "run_validated_case_state_extraction",
    "attach_llm_extraction",
]
