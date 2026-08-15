"""Post-analysis completeness checks and follow-up audit metadata formatting."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import time
import unicodedata
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any, Sequence
from uuid import UUID

import httpx

from app.config import settings
from app.services.chat.gap_and_followup.gap_analysis import AnthropicGapAnalysis
from app.services.chat.gap_and_followup.followup_policy import (
    AnthropicFollowUpPolicy,
)
from app.services.chat.gap_and_followup.prompts import (
    FOLLOWUP_POLICY_VERSION,
    FOLLOWUP_PROMPT_VERSION,
    GAP_ANALYSIS_PROMPT_VERSION,
    GAP_ANALYSIS_VERSION,
)
from app.services.chat.gap_and_followup.schemas import (
    ClarificationExchange,
    GapAnalysis,
    GapAnalysisResult,
    GapAnalyzer,
    GapItem,
    FollowUpDecision,
    FollowUpPolicy,
    FollowUpPolicyResult,
)
from app.services.chat.outcome_mapper import AssistantOutcome
from app.services.llm.core_llm import resolve_core_llm_target

logger = logging.getLogger("app.chat")


@dataclass(frozen=True)
class FollowUpResolution:
    """The gate result and the audit record carried into the final message."""

    outcome: AssistantOutcome | None
    metadata_json: dict[str, Any]


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


async def evaluate_followup_outcome(
    *,
    original_user_content: str,
    clarification_exchanges: Sequence[ClarificationExchange],
    followup_root_ordinal: int,
    source_run_id: UUID,
    policy: FollowUpPolicy | None = None,
    gap_analyzer: GapAnalyzer | None = None,
    case_state: Mapping[str, object] | None = None,
    analysis_answer: str | None = None,
    analysis_context: Mapping[str, object] | None = None,
) -> FollowUpResolution:
    """Run Gap Analysis, then the separate post-analysis follow-up policy."""

    round_number = len(clarification_exchanges) + 1
    prior_exchange_count = len(clarification_exchanges)
    gap_trace = _empty_gap_analysis_trace()

    def proceed_resolution(
        *,
        reason_code: str,
        stop_reason: str,
        **metadata_kwargs: Any,
    ) -> FollowUpResolution:
        return FollowUpResolution(
            outcome=None,
            metadata_json=_followup_metadata(
                source_run_id=source_run_id,
                followup_root_ordinal=followup_root_ordinal,
                round_number=round_number,
                prior_exchange_count=prior_exchange_count,
                action="proceed",
                question="",
                reason_code=reason_code,
                stop_reason=stop_reason,
                gap_analysis=gap_trace,
                **metadata_kwargs,
            ),
        )

    if not settings.chat_followup_policy_enabled:
        return proceed_resolution(
            reason_code="followup_policy_disabled",
            stop_reason="policy_disabled",
        )
    if len(clarification_exchanges) >= settings.chat_followup_max_rounds:
        return proceed_resolution(
            reason_code="max_rounds_reached",
            stop_reason="max_rounds_reached",
        )
    if clarification_exchanges and _answer_indicates_unavailable(
        clarification_exchanges[-1].answer
    ):
        return proceed_resolution(
            reason_code="answer_unavailable",
            stop_reason="answer_unavailable",
        )

    # A custom policy without a matching analyzer is retained as a compatibility
    # seam for old in-process callers and tests. The production default always
    # runs the provider-backed analyzer before the policy.
    compatibility_gap_analysis = gap_analyzer is None and policy is not None
    if compatibility_gap_analysis:
        gap_result = GapAnalysisResult(analysis=GapAnalysis(gaps=[]))
        gap_trace = _empty_gap_analysis_trace(status="compatibility_skipped")
    else:
        gap_started = time.perf_counter()
        try:
            active_gap_analyzer = (
                gap_analyzer()
                if isinstance(gap_analyzer, type)
                else (gap_analyzer or AnthropicGapAnalysis())
            )
            gap_kwargs = {
                "original_user_content": original_user_content,
                "clarification_exchanges": clarification_exchanges,
                "case_state": case_state,
                "analysis_answer": analysis_answer,
                "analysis_context": analysis_context,
            }
            raw_gap_result = await _invoke_policy_method(
                active_gap_analyzer.analyze,
                gap_kwargs,
            )
            gap_result = _coerce_gap_analysis_result(
                raw_gap_result,
                elapsed_ms=round((time.perf_counter() - gap_started) * 1000, 3),
            )
            gap_trace = _gap_analysis_trace(gap_result)
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - gap_started) * 1000, 3)
            failure_code = _followup_failure_code(exc)
            gap_trace = _empty_gap_analysis_trace(
                status="failed",
                latency_ms=elapsed_ms,
                failure_code=failure_code,
            )
            logger.warning(
                "Chat gap analysis failed open source_run_id=%s failure_code=%s",
                source_run_id,
                failure_code,
            )
            return proceed_resolution(
                reason_code="gap_analysis_failed_open",
                stop_reason="gap_analysis_failed_open",
                latency_ms=elapsed_ms,
                failure_code=failure_code,
            )

    started = time.perf_counter()
    try:
        active_policy = (
            policy()
            if isinstance(policy, type)
            else (policy or AnthropicFollowUpPolicy())
        )
        policy_kwargs = {
            "original_user_content": original_user_content,
            "clarification_exchanges": clarification_exchanges,
            "gap_analysis": gap_result.analysis,
            "case_state": case_state,
            "analysis_answer": analysis_answer,
            "analysis_context": analysis_context,
        }
        if hasattr(active_policy, "decide_with_metadata") and callable(
            getattr(active_policy, "decide_with_metadata")
        ):
            raw_result = await _invoke_policy_method(
                active_policy.decide_with_metadata,
                policy_kwargs,
            )
        else:
            raw_result = await _invoke_policy_method(
                active_policy.decide,
                policy_kwargs,
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
        return proceed_resolution(
            reason_code="policy_failed_open",
            stop_reason="policy_failed_open",
            latency_ms=elapsed_ms,
            failure_code=failure_code,
        )

    if decision.decision == "proceed":
        reason_code = decision.reason_code or (
            "unresolved_gaps_recorded"
            if gap_result.analysis.gaps
            else "sufficient_case_context"
        )
        return proceed_resolution(
            reason_code=reason_code,
            stop_reason="policy_proceed",
            decision=decision.decision,
            latency_ms=result.latency_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            provider=result.provider,
            model=result.model,
        )

    selected_gap = _selected_askable_gap(
        gap_result.analysis,
        decision.selected_gap,
        compatibility=compatibility_gap_analysis,
    )
    if selected_gap is None:
        return proceed_resolution(
            reason_code="policy_invalid_selection",
            stop_reason="policy_invalid_selection",
            decision="proceed",
            requested_selected_gap=decision.selected_gap,
            latency_ms=result.latency_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            provider=result.provider,
            model=result.model,
        )

    normalized_question = _normalized_question(decision.question)
    if any(
        _normalized_question(exchange.question) == normalized_question
        for exchange in clarification_exchanges
    ):
        return proceed_resolution(
            reason_code="duplicate_question",
            stop_reason="duplicate_question",
            decision="proceed",
            selected_gap=selected_gap.topic,
            latency_ms=result.latency_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            provider=result.provider,
            model=result.model,
        )

    reason_code = decision.reason_code or _gap_reason_code(selected_gap)
    metadata = _followup_metadata(
        source_run_id=source_run_id,
        followup_root_ordinal=followup_root_ordinal,
        round_number=round_number,
        prior_exchange_count=prior_exchange_count,
        action="ask_followup",
        question=decision.question,
        reason_code=reason_code,
        stop_reason="ask_followup",
        decision=decision.decision,
        selected_gap=selected_gap.topic,
        gap_analysis=gap_trace,
        latency_ms=result.latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        provider=result.provider,
        model=result.model,
        rag_skipped=True,
    )
    return FollowUpResolution(
        outcome=AssistantOutcome(
            content=decision.question,
            retrieval_context_id=None,
            metadata_json=metadata,
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
    gap_analyzer: GapAnalyzer | None = None,
    case_state: Mapping[str, object] | None = None,
    analysis_answer: str | None = None,
    analysis_context: Mapping[str, object] | None = None,
) -> AssistantOutcome | None:
    """Compatibility wrapper returning only the pending assistant outcome."""

    resolution = await evaluate_followup_outcome(
        original_user_content=original_user_content,
        clarification_exchanges=clarification_exchanges,
        followup_root_ordinal=followup_root_ordinal,
        source_run_id=source_run_id,
        policy=policy,
        gap_analyzer=gap_analyzer,
        case_state=case_state,
        analysis_answer=analysis_answer,
        analysis_context=analysis_context,
    )
    return resolution.outcome


async def _invoke_policy_method(
    method: Any,
    kwargs: dict[str, object],
) -> object:
    """Call old test/custom policies without dropping new completeness context."""

    try:
        parameters = inspect.signature(method).parameters
    except (TypeError, ValueError):
        parameters = {}
    accepts_kwargs = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
    if not accepts_kwargs and parameters:
        kwargs = {key: value for key, value in kwargs.items() if key in parameters}
    return await method(**kwargs)


def _coerce_gap_analysis_result(
    raw_result: object,
    *,
    elapsed_ms: float,
) -> GapAnalysisResult:
    if isinstance(raw_result, GapAnalysisResult):
        return GapAnalysisResult(
            analysis=GapAnalysis.model_validate(raw_result.analysis),
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
    return GapAnalysisResult(
        analysis=GapAnalysis.model_validate(raw_result),
        latency_ms=elapsed_ms,
    )


def _empty_gap_analysis_trace(
    *,
    status: str = "not_run",
    latency_ms: float | None = None,
    failure_code: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "version": GAP_ANALYSIS_VERSION,
        "prompt_version": GAP_ANALYSIS_PROMPT_VERSION,
        "gaps": [],
        "latency_ms": latency_ms,
        "input_tokens": None,
        "output_tokens": None,
        "provider": None,
        "model": None,
        "failure_code": failure_code,
    }


def _gap_analysis_trace(result: GapAnalysisResult) -> dict[str, Any]:
    return {
        "status": "completed",
        "version": GAP_ANALYSIS_VERSION,
        "prompt_version": GAP_ANALYSIS_PROMPT_VERSION,
        "gaps": [gap.model_dump(mode="json") for gap in result.analysis.gaps],
        "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "provider": result.provider,
        "model": result.model,
        "failure_code": None,
    }


def _selected_askable_gap(
    analysis: GapAnalysis,
    selected_gap: str | None,
    *,
    compatibility: bool,
) -> GapItem | None:
    if not isinstance(selected_gap, str) or not selected_gap.strip():
        return None
    if compatibility:
        return GapItem(
            topic=selected_gap,
            status="NOT_PROVIDED",
            description="Legacy policy supplied a selected follow-up topic.",
            affects="The legacy follow-up policy contract.",
            reason="Retained only for compatibility with injected policies.",
            priority="high",
            askable=True,
        )
    normalized = _normalized_question(selected_gap)
    eligible_gaps = [
        gap
        for gap in analysis.gaps
        if (
            gap.priority in ("high", "medium")
            and gap.askable
            and gap.status != "EXPLICITLY_UNKNOWN"
        )
    ]
    if not eligible_gaps:
        return None
    priority_rank = {"high": 2, "medium": 1}
    highest_priority = max(priority_rank[gap.priority] for gap in eligible_gaps)
    for gap in analysis.gaps:
        if _normalized_question(gap.topic) != normalized:
            continue
        if (
            gap.priority not in ("high", "medium")
            or not gap.askable
            or gap.status == "EXPLICITLY_UNKNOWN"
            or priority_rank[gap.priority] != highest_priority
        ):
            return None
        return gap
    return None


def _gap_reason_code(gap: GapItem) -> str:
    return {
        "NOT_PROVIDED": "material_incident_fact_missing",
        "AMBIGUOUS": "material_incident_fact_ambiguous",
        "CONFLICTING": "material_incident_fact_conflicting",
        "EXPLICITLY_UNKNOWN": "unresolved_gaps_recorded",
    }[gap.status]


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
    decision: str | None = None,
    selected_gap: str | None = None,
    requested_selected_gap: str | None = None,
    gap_analysis: dict[str, Any] | None = None,
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
            "decision": decision or action,
            "question": question,
            "selected_gap": selected_gap,
            "requested_selected_gap": requested_selected_gap,
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
            "gap_analysis": deepcopy(
                gap_analysis or _empty_gap_analysis_trace()
            ),
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
