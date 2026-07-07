from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

EvidenceStatus = Literal["confirmed", "reported", "inferred", "unknown"]
ReviewStatus = Literal["draft", "ai_generated", "reviewed", "approved"]
SourceType = Literal[
    "user_input",
    "uploaded_file",
    "log",
    "rag_source",
    "mitre_source",
    "legal_source",
]
Confidence = Literal["low", "medium", "high"]


class EvidenceReference(BaseModel):
    evidence_id: str
    source_type: SourceType
    source_name: str
    excerpt: str | None = None
    page_number: int | None = None
    line_reference: str | None = None
    file_hash_sha256: str | None = None
    content_type: str | None = None
    uploaded_at: str | None = None
    extraction_method: str | None = None


__all__ = [
    "Confidence",
    "EvidenceReference",
    "EvidenceStatus",
    "ReviewStatus",
    "SourceType",
]
