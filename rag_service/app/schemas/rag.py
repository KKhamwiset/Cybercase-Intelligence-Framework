from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from RAG import MitreTableRow


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    use_agent: bool = True


class QueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Always "completed" — the pipeline no longer pauses for clarification.
    status: Literal["completed"]
    retrieval_context_id: str | None
    context: str
    # MITRE ATT&CK mapping table selected inside rag-service. The generated
    # answer may be used internally for relevance, but never crosses this
    # response boundary.
    mitre_table: list[MitreTableRow] = Field(default_factory=list)

    @field_validator("retrieval_context_id", mode="before")
    @classmethod
    def normalize_empty_retrieval_context_id(cls, value: Any) -> Any:
        return None if value == "" else value


class RetrievalContextSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retrieval_context_id: str
    query: str = ""
    context: str
    rag_result: dict[str, Any] = Field(default_factory=dict)
    mitre_table: list[MitreTableRow] = Field(default_factory=list)


class ReviewStatusRequest(BaseModel):
    review_status: Literal["draft", "ai_generated", "reviewed", "approved"]
