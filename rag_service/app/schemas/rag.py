from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from RAG import EvidenceReference


class QueryRequest(BaseModel):
    query: str
    use_agent: bool = True
    report_type: str = "overview"
    legal: bool = False
    force_generate: bool = False
    evidence_registry: list[EvidenceReference] = Field(default_factory=list)
    retrieval_context_id: str = ""


class QueryResponse(BaseModel):
    status: str
    answer: str = ""
    followup_question: str = ""
    session_id: str = ""
    retrieval_context_id: str = ""


class ResumeRequest(BaseModel):
    session_id: str
    answer: str


class ReviewStatusRequest(BaseModel):
    review_status: Literal["draft", "ai_generated", "reviewed", "approved"]
