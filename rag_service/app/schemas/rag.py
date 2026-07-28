from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from RAG import MitreTableRow


class QueryRequest(BaseModel):
    query: str
    use_agent: bool = True


class QueryResponse(BaseModel):
    # Always "completed" — the pipeline no longer pauses for clarification.
    status: str
    answer: str = ""
    retrieval_context_id: str = ""
    # Noise-filtered MITRE ATT&CK mapping table derived from the raw retrieval
    # results (answer-grounded + score-threshold filtering; see mitre_table.py).
    mitre_table: list[MitreTableRow] = Field(default_factory=list)


class RetrievalContextSnapshot(BaseModel):
    retrieval_context_id: str
    query: str = ""
    context: str
    rag_result: dict[str, Any] = Field(default_factory=dict)
    answer: str = ""
    mitre_table: list[MitreTableRow] = Field(default_factory=list)


class ReviewStatusRequest(BaseModel):
    review_status: Literal["draft", "ai_generated", "reviewed", "approved"]
