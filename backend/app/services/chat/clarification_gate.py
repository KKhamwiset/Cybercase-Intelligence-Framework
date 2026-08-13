"""Pre-retrieval clarification checks, follow-up decision policy evaluation, and audit metadata formatting."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass, replace
from typing import Any, Sequence
from uuid import UUID

import httpx

from app.config import settings
from app.services.chat.followup_policy import (
    AnthropicFollowUpPolicy,
    ClarificationExchange,
    FOLLOWUP_POLICY_VERSION,
    FOLLOWUP_PROMPT_VERSION,
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
        active_policy = policy() if isinstance(policy, type) else (policy or AnthropicFollowUpPolicy())
        if hasattr(active_policy, "decide_with_metadata") and callable(getattr(active_policy, "decide_with_metadata")):
            raw_result = await active_policy.decide_with_metadata(
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
