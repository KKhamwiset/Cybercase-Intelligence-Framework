"""Data structures and outcome mapping utilities for RAG context payloads and assistant outcomes."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.schemas.chat.rag import QueryResponse
from app.services.case_analysis import CASE_ANALYSIS_PROMPT_VERSION
from app.services.chat.rag_client import RagCallFailure
from app.services.extraction.llm_extraction import EXTRACTION_METADATA_KEY


@dataclass(frozen=True)
class RagContextPayload:
    """Validated retrieval data that must be committed with its case state."""

    retrieval_context_id: str
    context: str
    mitre_table: tuple[dict[str, object], ...]

    def to_analysis_context(self) -> dict[str, object]:
        """Return a defensive snapshot for read-only Main analysis."""

        return {
            "retrieved_context": self.context,
            "retrieval_context_id": self.retrieval_context_id,
            "mitre_table": deepcopy(list(self.mitre_table)),
            "previous_analysis": None,
        }


@dataclass(frozen=True)
class AssistantOutcome:
    content: str
    retrieval_context_id: str | None
    metadata_json: dict[str, Any]
    thread_status: str
    active_rag_session_id: str | None
    validated_case_state_json: dict[str, object] | None = None
    rag_context_payload: RagContextPayload | None = None


def map_rag_response(response: QueryResponse) -> dict[str, object]:
    """Map retrieval-only wire data into bounded Main-analysis context."""

    return {
        "retrieved_context": response.context,
        "retrieval_context_id": (
            str(response.retrieval_context_id)
            if response.retrieval_context_id is not None
            else None
        ),
        "mitre_table": [
            row.model_dump(mode="json")
            for row in response.mitre_table
        ],
        "previous_analysis": None,
    }


def _validated_rag_context_payload(
    response: QueryResponse,
) -> RagContextPayload:
    """Fail closed unless retrieval data is safe to persist before analysis."""

    retrieval_context_id = response.retrieval_context_id
    if isinstance(retrieval_context_id, str):
        retrieval_context_id = retrieval_context_id.strip()
    if (
        not isinstance(retrieval_context_id, str)
        or not retrieval_context_id
        or len(retrieval_context_id) > 160
        or not response.context.strip()
    ):
        raise RagCallFailure(
            "rag_invalid_response",
            "RAG service returned an invalid response",
        )

    return RagContextPayload(
        retrieval_context_id=retrieval_context_id,
        context=response.context,
        mitre_table=tuple(
            row.model_dump(mode="json")
            for row in response.mitre_table
        ),
    )


def map_initial_case_analysis_response(
    answer: str,
    *,
    rag_context_payload: RagContextPayload,
    validated_case_state_json: dict[str, object],
    extraction_metadata: dict[str, Any],
    followup_metadata_json: dict[str, Any],
) -> AssistantOutcome:
    """Create the one durable initial Main analysis plus its grounding audit."""

    metadata_json = deepcopy(followup_metadata_json)
    metadata_json.update(
        {
            EXTRACTION_METADATA_KEY: deepcopy(extraction_metadata),
            "analysis_kind": "grounded_main_analysis",
            "retrieved_context": rag_context_payload.context,
            "mitre_table": deepcopy(list(rag_context_payload.mitre_table)),
            "chat_action": {
                "action": "initial_analysis",
                "route": "analysis",
                "grounded_main_analysis": True,
                "state_mutated": True,
                "case_state_version_created": True,
                "rag_invoked": True,
                "retrieval_context_reused": False,
                "prompt_version": CASE_ANALYSIS_PROMPT_VERSION,
            },
        }
    )
    return AssistantOutcome(
        content=answer,
        retrieval_context_id=rag_context_payload.retrieval_context_id,
        metadata_json=metadata_json,
        thread_status="answered",
        active_rag_session_id=None,
        validated_case_state_json=validated_case_state_json,
        rag_context_payload=rag_context_payload,
    )


def map_case_analysis_response(
    answer: str,
    *,
    analysis_context: dict[str, object],
) -> AssistantOutcome:
    """Persist an ASK answer while carrying forward the prior retrieval handle."""

    retrieval_context_id = analysis_context.get("retrieval_context_id")
    if not isinstance(retrieval_context_id, str):
        retrieval_context_id = None
    mitre_table = analysis_context.get("mitre_table", [])
    if not isinstance(mitre_table, list):
        mitre_table = []
    return AssistantOutcome(
        content=answer,
        retrieval_context_id=retrieval_context_id,
        metadata_json={
            "mitre_table": deepcopy(mitre_table),
            "chat_action": {
                "action": "ask",
                "route": "analysis",
                "state_mutated": False,
                "case_state_version_created": False,
                "rag_invoked": False,
                "retrieval_context_reused": True,
                "prompt_version": CASE_ANALYSIS_PROMPT_VERSION,
            },
        },
        thread_status="answered",
        active_rag_session_id=None,
    )
