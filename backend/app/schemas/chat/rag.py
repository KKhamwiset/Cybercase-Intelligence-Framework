from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    model_config = ConfigDict(extra="allow")

    status: Literal["completed"]
    answer: str = ""
    retrieval_context_id: str | None = None
    mitre_table: list[MitreTableRow] = Field(default_factory=list)

    @field_validator("retrieval_context_id", mode="before")
    @classmethod
    def normalize_empty_retrieval_context_id(cls, value: Any) -> Any:
        """Treat the RAG service's empty-string sentinel as no frozen context."""

        return None if value == "" else value


__all__ = [
    "MitreTableRow",
    "QueryRequest",
    "QueryResponse",
    "RagQueryRequest",
]
