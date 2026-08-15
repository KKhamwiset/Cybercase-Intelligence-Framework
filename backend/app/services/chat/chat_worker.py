'''Claim, execute, and finalize persistent background chat runs.'''

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass, replace
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
from app.services.chat.case_state_retrieval import (
    project_case_state_to_retrieval_query,
)
from app.services.chat.case_state_mutation import (
    MUTATION_METADATA_KEY,
    CaseStateDelta,
    CaseStateMutationFailure,
    CaseStateDeltaInput,
    apply_case_state_delta,
    run_case_state_delta_extraction,
)
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
)
from app.services.chat.outcome_mapper import (
    AssistantOutcome,
    RagContextPayload,
    _validated_rag_context_payload,
    build_merged_extraction_metadata,
    map_case_analysis_response,
    map_case_state_mutation_response,
    map_case_state_no_change_response,
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
    pending_question: str | None = None
    extraction_input: ExtractionInput | None = None
    post_answer_action: str | None = None
    clarification_answer: bool = False
    request_message_id: UUID | None = None
    case_state_version_id: UUID | None = None
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
            clarification_answer = (
                isinstance(request_payload, dict)
                and request_payload.get("clarification_answer") is True
            )

            case_state_json: dict[str, object] | None = None
            analysis_context: dict[str, object] | None = None
            case_state_version_id: UUID | None = None
            requested_parent_version_id: UUID | None = None
            if isinstance(request_payload, dict):
                raw_parent_version_id = request_payload.get("case_state_version_id")
                if raw_parent_version_id is not None:
                    try:
                        requested_parent_version_id = UUID(str(raw_parent_version_id))
                    except (TypeError, ValueError, AttributeError):
                        requested_parent_version_id = None
            if post_answer_action in ('ask', 'add_case_info'):
                pointer_result = await self.db.execute(
                    select(ChatThread.current_case_state_version_id).where(
                        ChatThread.id == run.thread_id,
                    )
                )
                current_state_version_id = pointer_result.scalar_one_or_none()
                state_lookup_id = (
                    requested_parent_version_id
                    if post_answer_action == "add_case_info"
                    and requested_parent_version_id is not None
                    else current_state_version_id
                )
                if state_lookup_id is not None:
                    case_state_version_id = state_lookup_id
                    state_result = await self.db.execute(
                        select(CaseStateVersion).where(
                            CaseStateVersion.id == state_lookup_id,
                            CaseStateVersion.thread_id == run.thread_id,
                        )
                    )
                    case_state = state_result.scalar_one_or_none()
                    if case_state is not None and isinstance(
                        case_state.state_json,
                        dict,
                    ):
                        case_state_json = deepcopy(case_state.state_json)
                        if post_answer_action == 'ask':
                            rag_context_result = await self.db.execute(
                                select(RagContext).where(
                                    RagContext.thread_id == run.thread_id,
                                    RagContext.case_state_version_id
                                    == state_lookup_id,
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
            pending_question: str | None = None
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
                    pending_question = chain.pending_question
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
            if post_answer_action in (None, "add_case_info"):
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
                pending_question=pending_question,
                followup_root_ordinal=followup_root_ordinal,
                extraction_input=extraction_input,
                post_answer_action=post_answer_action,
                clarification_answer=clarification_answer,
                request_message_id=run.request_message_id,
                case_state_version_id=case_state_version_id,
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

            has_mutation = (
                outcome.case_state_delta_json is not None
                or outcome.expected_parent_case_state_version_id is not None
            )
            if has_mutation and (
                not has_case_state
                or not has_rag_context
                or outcome.case_state_delta_json is None
                or outcome.expected_parent_case_state_version_id is None
            ):
                raise ValueError(
                    "A Case State mutation must include its merged snapshot, "
                    "delta, and fresh RAG context"
                )

            case_state_version: CaseStateVersion | None = None
            if has_mutation:
                expected_parent_id = outcome.expected_parent_case_state_version_id
                if thread.current_case_state_version_id != expected_parent_id:
                    raise CaseStateMutationFailure(
                        "case_state_stale_parent",
                        "The Case State changed before this mutation completed",
                    )
                parent_result = await self.db.execute(
                    select(CaseStateVersion)
                    .where(
                        CaseStateVersion.id == expected_parent_id,
                        CaseStateVersion.thread_id == thread.id,
                    )
                    .with_for_update()
                )
                parent_version = parent_result.scalar_one_or_none()
                if parent_version is None:
                    raise CaseStateMutationFailure(
                        "case_state_parent_missing",
                        "The mutation parent Case State could not be loaded",
                    )
                try:
                    delta = CaseStateDelta.model_validate(
                        outcome.case_state_delta_json
                    )
                    chat_action = outcome.metadata_json.get("chat_action")
                    allow_empty_delta = (
                        isinstance(chat_action, dict)
                        and chat_action.get("action") == "clarification_answer"
                    )
                    if not delta.changes and not allow_empty_delta:
                        raise ValueError("an empty delta cannot create a child version")
                    merged_state = apply_case_state_delta(
                        parent_version.state_json,
                        delta,
                        source_message_id=run.request_message_id,
                    )
                except Exception as exc:
                    if isinstance(exc, CaseStateMutationFailure):
                        raise
                    raise CaseStateMutationFailure(
                        "case_state_delta_invalid",
                        "The persisted mutation delta failed deterministic validation",
                    ) from exc
                if merged_state != outcome.validated_case_state_json:
                    raise CaseStateMutationFailure(
                        "case_state_delta_invalid",
                        "The merged Case State does not match its delta",
                    )
                case_state_version = CaseStateVersion(
                    id=uuid4(),
                    thread_id=thread.id,
                    version=parent_version.version + 1,
                    parent_version_id=parent_version.id,
                    trigger_message_id=run.request_message_id,
                    delta_json=delta.model_dump(mode="json"),
                    state_json=deepcopy(outcome.validated_case_state_json),
                )
                self.db.add(case_state_version)
                await self.db.flush()
            elif (
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

            if has_mutation and case_state_version is not None:
                thread.current_case_state_version_id = case_state_version.id

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
                for audit_key in (
                    "chat_followup",
                    EXTRACTION_METADATA_KEY,
                    MUTATION_METADATA_KEY,
                ):
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


def _log_stage(stage_name: str, run_id: UUID | str, detail: str = "") -> None:
    sep = "=" * 70
    msg = f"\n{sep}\n[CHAT RUN {run_id}] ▶ STAGE: {stage_name}"
    if detail:
        msg += f" — {detail}"
    msg += f"\n{sep}"
    print(msg, flush=True)
    logger.info("Chat run %s entering stage: %s %s", run_id, stage_name, detail)


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

    _log_stage(
        "STARTING RUN",
        run_id,
        f"action={claimed_run.post_answer_action or 'initial_query'}",
    )
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
            _log_stage("EXTRACTING CASE STATE DELTA", run_id)
            if not isinstance(claimed_run.case_state_json, dict):
                raise CaseStateMutationFailure(
                    'case_state_parent_missing',
                    'The current Case State could not be loaded for mutation',
                )
            if claimed_run.case_state_version_id is None:
                raise CaseStateMutationFailure(
                    'case_state_parent_missing',
                    'The current Case State version could not be loaded for mutation',
                )
            if claimed_run.request_message_id is None:
                raise CaseStateMutationFailure(
                    'case_state_mutation_input_missing',
                    'The mutation source message could not be identified',
                )

            try:
                delta_input = CaseStateDeltaInput(
                    current_case_state=deepcopy(claimed_run.case_state_json),
                    new_user_message=claimed_run.content,
                    source_message_id=claimed_run.request_message_id,
                    mutation_intent='add_case_info',
                    pending_question=(
                        claimed_run.pending_question
                        if claimed_run.clarification_answer
                        else None
                    ),
                )
            except (TypeError, ValueError) as exc:
                raise CaseStateMutationFailure(
                    'case_state_mutation_input_invalid',
                    'The explicit mutation message could not be prepared',
                ) from exc
            delta, mutation_metadata = await run_case_state_delta_extraction(
                delta_input,
                adapter=extraction_adapter,
            )
            followup_metadata_json = {MUTATION_METADATA_KEY: mutation_metadata}
            if delta is None:
                raise CaseStateMutationFailure(
                    str(mutation_metadata.get('failure_code', 'case_state_delta_failed')),
                    str(
                        mutation_metadata.get(
                            'failure_message',
                            'The Case State delta failed validation',
                        )
                    ),
                )

            if not delta.changes and not claimed_run.clarification_answer:
                _log_stage("NO CHANGES DETECTED (Skipping RAG)", run_id)
                outcome = map_case_state_no_change_response(
                    mutation_metadata=mutation_metadata,
                )
            else:
                merged_case_state_json = apply_case_state_delta(
                    claimed_run.case_state_json,
                    delta,
                    source_message_id=claimed_run.request_message_id,
                )
                retrieval_query = project_case_state_to_retrieval_query(
                    merged_case_state_json,
                )
                _log_stage("RAG RETRIEVAL (Querying GraphRAG)", run_id)
                response = await (rag_call or request_rag)(retrieval_query)
                rag_context_payload = _validated_rag_context_payload(response)
                analysis_context = rag_context_payload.to_analysis_context()
                _log_stage("ANALYZING UPDATED CASE OVERVIEW", run_id)
                answer = await (ask_call or request_case_analysis)(
                    mode='case_overview',
                    case_state_json=merged_case_state_json,
                    analysis_context=analysis_context,
                    question=None,
                )
                if not isinstance(answer, str) or not answer.strip():
                    raise CaseAnalysisFailure(
                        'analysis_invalid_response',
                        'The mutation Main Case Analysis returned no answer',
                    )
                extraction_metadata = build_merged_extraction_metadata(
                    merged_case_state_json,
                    source_message_ids=_source_message_ids_for_run(claimed_run),
                    mutation_metadata=mutation_metadata,
                )
                _log_stage("EVALUATING CLARIFICATION & FOLLOWUP POLICY", run_id)
                followup_resolution = await evaluate_followup_outcome(
                    original_user_content=claimed_run.original_user_content,
                    clarification_exchanges=claimed_run.clarification_exchanges,
                    followup_root_ordinal=claimed_run.followup_root_ordinal,
                    source_run_id=claimed_run.id,
                    policy=policy,
                    case_state=merged_case_state_json,
                    analysis_answer=answer.strip(),
                    analysis_context=analysis_context,
                )
                action = (
                    "clarification_answer"
                    if claimed_run.clarification_answer
                    else "add_case_info"
                )
                if followup_resolution.outcome is not None:
                    outcome = _attach_post_analysis_followup_outcome(
                        followup_resolution.outcome,
                        rag_context_payload=rag_context_payload,
                        validated_case_state_json=merged_case_state_json,
                        extraction_metadata=extraction_metadata,
                        action=action,
                        delta_json=delta.model_dump(mode='json'),
                        expected_parent_case_state_version_id=(
                            claimed_run.case_state_version_id
                        ),
                        mutation_metadata=mutation_metadata,
                    )
                else:
                    followup_metadata_json = {
                        **_mark_followup_rag_invoked_metadata(
                            followup_resolution.metadata_json
                        ),
                        EXTRACTION_METADATA_KEY: extraction_metadata,
                    }
                    outcome = map_case_state_mutation_response(
                        answer.strip(),
                        rag_context_payload=rag_context_payload,
                        merged_case_state_json=merged_case_state_json,
                        delta_json=delta.model_dump(mode='json'),
                        expected_parent_case_state_version_id=(
                            claimed_run.case_state_version_id
                        ),
                        mutation_metadata=mutation_metadata,
                        extraction_metadata=extraction_metadata,
                        followup_metadata_json=followup_metadata_json,
                        action=action,
                    )
            _log_stage("PERSISTING OUTCOME & COMPLETING RUN", run_id)
            async with async_session() as finalize_db:
                await ChatRunWorker(finalize_db).complete_run(
                    run_id,
                    worker_id,
                    outcome,
                )
            print(f"\n[CHAT RUN {run_id}] ✔ RUN COMPLETED SUCCESSFULLY\n{'='*70}\n", flush=True)
            return

        if claimed_run.post_answer_action == 'ask':
            _log_stage("ANSWERING QUESTION (ASK Mode)", run_id)
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
                mode='question_answer',
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
            _log_stage("PERSISTING ASK OUTCOME", run_id)
            async with async_session() as finalize_db:
                await ChatRunWorker(finalize_db).complete_run(
                    run_id,
                    worker_id,
                    outcome,
                )
            print(f"\n[CHAT RUN {run_id}] ✔ ASK COMPLETED SUCCESSFULLY\n{'='*70}\n", flush=True)
            return

        _log_stage("EXTRACTING BASELINE CASE STATE", run_id)
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

        _log_stage("RAG RETRIEVAL (Querying GraphRAG)", run_id)
        retrieval_query = project_case_state_to_retrieval_query(
            validated_case_state_json,
        )
        response = await (rag_call or request_rag)(retrieval_query)
        rag_context_payload = _validated_rag_context_payload(response)
        analysis_context = rag_context_payload.to_analysis_context()
        _log_stage("ANALYZING INITIAL CASE OVERVIEW", run_id)
        answer = await (ask_call or request_case_analysis)(
            mode='case_overview',
            case_state_json=validated_case_state_json,
            analysis_context=analysis_context,
            question=None,
        )
        if not isinstance(answer, str) or not answer.strip():
            raise CaseAnalysisFailure(
                'analysis_invalid_response',
                'The initial Main Case Analysis returned no answer',
            )
        _log_stage("EVALUATING CLARIFICATION & FOLLOWUP POLICY", run_id)
        followup_resolution = await evaluate_followup_outcome(
            original_user_content=claimed_run.original_user_content,
            clarification_exchanges=claimed_run.clarification_exchanges,
            followup_root_ordinal=claimed_run.followup_root_ordinal,
            source_run_id=claimed_run.id,
            policy=policy,
            case_state=validated_case_state_json,
            analysis_answer=answer.strip(),
            analysis_context=analysis_context,
        )
        if followup_resolution.outcome is not None:
            outcome = _attach_post_analysis_followup_outcome(
                followup_resolution.outcome,
                rag_context_payload=rag_context_payload,
                validated_case_state_json=validated_case_state_json,
                extraction_metadata=extraction_metadata,
                action="initial_analysis",
            )
        else:
            followup_metadata_json = {
                **_mark_followup_rag_invoked_metadata(
                    followup_resolution.metadata_json
                ),
                EXTRACTION_METADATA_KEY: extraction_metadata,
            }
            outcome = map_initial_case_analysis_response(
                answer.strip(),
                rag_context_payload=rag_context_payload,
                validated_case_state_json=validated_case_state_json,
                extraction_metadata=extraction_metadata,
                followup_metadata_json=followup_metadata_json,
            )

        _log_stage("PERSISTING OUTCOME & COMPLETING RUN", run_id)
        async with async_session() as finalize_db:
            await ChatRunWorker(finalize_db).complete_run(
                run_id,
                worker_id,
                outcome,
            )
        print(f"\n[CHAT RUN {run_id}] ✔ INITIAL RUN COMPLETED SUCCESSFULLY\n{'='*70}\n", flush=True)
    except ExtractionStageFailure as exc:
        print(f"\n[CHAT RUN {run_id}] ✖ FAILED AT EXTRACTION STAGE: [{exc.code}] {exc.message}\n{'='*70}\n", flush=True)
        await _record_failure(
            run_id,
            worker_id,
            exc.code,
            exc.message,
            followup_metadata_json=exc.metadata_json,
        )
    except RagCallFailure as exc:
        print(f"\n[CHAT RUN {run_id}] ✖ FAILED AT RAG RETRIEVAL STAGE: [{exc.code}] {exc.message}\n{'='*70}\n", flush=True)
        await _record_failure(
            run_id,
            worker_id,
            exc.code,
            exc.message,
            followup_metadata_json=followup_metadata_json,
        )
    except CaseStateMutationFailure as exc:
        print(f"\n[CHAT RUN {run_id}] ✖ FAILED AT MUTATION STAGE: [{exc.code}] {exc.message}\n{'='*70}\n", flush=True)
        await _record_failure(
            run_id,
            worker_id,
            exc.code,
            exc.message,
            followup_metadata_json=followup_metadata_json,
        )
    except CaseAnalysisFailure as exc:
        print(f"\n[CHAT RUN {run_id}] ✖ FAILED AT ANALYSIS STAGE: [{exc.code}] {exc.message}\n{'='*70}\n", flush=True)
        await _record_failure(
            run_id,
            worker_id,
            exc.code,
            exc.message,
            followup_metadata_json=followup_metadata_json,
        )
    except Exception as exc:
        print(f"\n[CHAT RUN {run_id}] ✖ FAILED WITH UNEXPECTED ERROR: {exc}\n{'='*70}\n", flush=True)
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


def _source_message_ids_for_run(claimed_run: ClaimedChatRun) -> list[UUID]:
    if claimed_run.extraction_input is not None:
        return [
            message.message_id for message in claimed_run.extraction_input.messages
        ]
    if claimed_run.request_message_id is not None:
        return [claimed_run.request_message_id]
    return []


def _attach_post_analysis_followup_outcome(
    outcome: AssistantOutcome,
    *,
    rag_context_payload: RagContextPayload,
    validated_case_state_json: dict[str, object],
    extraction_metadata: dict[str, Any],
    action: str,
    delta_json: dict[str, object] | None = None,
    expected_parent_case_state_version_id: UUID | None = None,
    mutation_metadata: dict[str, Any] | None = None,
) -> AssistantOutcome:
    """Carry the latest analysis artifacts through the pending-follow-up turn."""

    marked = _mark_followup_rag_invoked(outcome, outcome.metadata_json)
    metadata = deepcopy(marked.metadata_json)
    metadata.update(
        {
            EXTRACTION_METADATA_KEY: deepcopy(extraction_metadata),
            "analysis_kind": "grounded_main_analysis",
            "retrieved_context": rag_context_payload.context,
            "mitre_table": deepcopy(list(rag_context_payload.mitre_table)),
            "chat_action": {
                "action": action,
                "route": "analysis",
                "grounded_main_analysis": True,
                "state_mutated": True,
                "case_state_version_created": True,
                "rag_invoked": True,
                "retrieval_context_reused": False,
                "analysis_mode": "case_overview",
            },
        }
    )
    if delta_json is not None:
        metadata["case_state_delta"] = deepcopy(delta_json)
    if mutation_metadata is not None:
        metadata["chat_mutation"] = deepcopy(mutation_metadata)
    return replace(
        marked,
        retrieval_context_id=rag_context_payload.retrieval_context_id,
        metadata_json=metadata,
        validated_case_state_json=deepcopy(validated_case_state_json),
        rag_context_payload=rag_context_payload,
        case_state_delta_json=(deepcopy(delta_json) if delta_json is not None else None),
        expected_parent_case_state_version_id=expected_parent_case_state_version_id,
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
    "CaseStateDelta",
    "CaseStateMutationFailure",
    "apply_case_state_delta",
    "run_case_state_delta_extraction",
]
