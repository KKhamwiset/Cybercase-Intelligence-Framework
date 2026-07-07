from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RagQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    use_agent: bool = True


class QueryRequest(RagQueryRequest):
    pass


class MitreTableRow(BaseModel):
    """One entry of the MITRE mapping table produced by the RAG service."""

    technique_id: str = ""
    name: str
    entity_type: str = ""
    tactic: str | None = None
    score: float | None = None
    source: Literal["vector", "graph"] = "vector"
    relevance: Literal["cited_in_answer", "retrieved_only"] = "retrieved_only"
    description: str = ""
    mitre_url: str | None = None


class QueryResponse(BaseModel):
    status: Literal["completed", "followup"]
    answer: str = ""
    followup_question: str = ""
    session_id: str = ""
    retrieval_context_id: str = ""
    mitre_table: list[MitreTableRow] = Field(default_factory=list)


class ResumeRequest(BaseModel):
    session_id: str
    answer: str


__all__ = [
    "MitreTableRow",
    "QueryRequest",
    "QueryResponse",
    "RagQueryRequest",
    "ResumeRequest",
]
