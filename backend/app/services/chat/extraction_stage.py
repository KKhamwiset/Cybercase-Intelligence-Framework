"""Pre-retrieval LLM Case State baseline extraction orchestration."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from app.config import settings
from app.services.chat.outcome_mapper import AssistantOutcome
from app.services.extraction.llm_extraction import (
    BASELINE_EXTRACTION_MODE,
    BASELINE_EXTRACTION_PROMPT_VERSION,
    BASELINE_EXTRACTION_VERSION,
    EXTRACTION_METADATA_KEY,
    ExtractionModelAdapter,
    run_baseline_extraction,
)
from app.services.llm.core_llm import resolve_core_llm_target

if TYPE_CHECKING:
    from app.services.chat.chat_worker import ClaimedChatRun

logger = logging.getLogger("app.chat")


class ExtractionStageFailure(Exception):
    """Fail-closed initial orchestration error with extraction audit data."""

    def __init__(
        self,
        code: str,
        message: str,
        metadata_json: dict[str, Any],
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.metadata_json = metadata_json


async def run_validated_case_state_extraction(
    claimed_run: ClaimedChatRun,
    *,
    adapter: ExtractionModelAdapter | None = None,
) -> tuple[dict[str, object] | None, dict[str, Any]]:
    """Run extraction before retrieval and return only validated Case State."""

    if claimed_run.extraction_input is None:
        return None, {
            "version": BASELINE_EXTRACTION_VERSION,
            "mode": BASELINE_EXTRACTION_MODE,
            "status": "failed",
            "prompt_version": BASELINE_EXTRACTION_PROMPT_VERSION,
            "validation_status": "failed",
            "failure_code": "extraction_input_missing",
            "failure_message": "The extraction source packet was not available",
        }

    extraction_input = claimed_run.extraction_input
    validated_case_state_json: dict[str, object] | None = None
    try:
        result = await run_baseline_extraction(
            extraction_input,
            adapter=adapter,
        )
        extraction_metadata = result.metadata(extraction_input)
        if result.status == "candidate" and result.extraction is not None:
            validated_case_state_json = result.extraction.model_dump(mode="json")
    except Exception:
        # Extraction is mandatory before retrieval/Main analysis. Preserve a
        # stable failure record if it fails outside typed provider handling.
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

    return validated_case_state_json, extraction_metadata


async def attach_llm_extraction(
    outcome: AssistantOutcome,
    claimed_run: ClaimedChatRun,
    *,
    adapter: ExtractionModelAdapter | None = None,
) -> AssistantOutcome:
    """Compatibility helper for callers that already have an outcome."""

    if outcome.thread_status not in ("idle", "answered"):
        return outcome
    validated_case_state_json, extraction_metadata = (
        await run_validated_case_state_extraction(
            claimed_run,
            adapter=adapter,
        )
    )
    metadata = dict(outcome.metadata_json)
    metadata[EXTRACTION_METADATA_KEY] = extraction_metadata
    return replace(
        outcome,
        metadata_json=metadata,
        validated_case_state_json=validated_case_state_json,
    )
