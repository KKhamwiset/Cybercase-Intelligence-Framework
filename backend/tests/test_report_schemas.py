import pytest
from pydantic import ValidationError

from app.routers.report import hash_bytes_sha256
from app.schemas.rag import (
    CaseFact,
    CaseFactPack,
    CaseInformationCompleteness,
    CompletenessField,
    EvidenceReference,
    LegalRelevanceAssessment,
)


def _completeness() -> CaseInformationCompleteness:
    return CaseInformationCompleteness(
        percentage=20,
        status="Incomplete - follow-up required",
        missing_fields=["incident date/time"],
        fields=[
            CompletenessField(
                field_id="incident_date_time",
                label="incident date/time",
                present=False,
                evidence_ids=[],
            )
        ],
    )


def test_sha256_evidence_hashing() -> None:
    assert (
        hash_bytes_sha256(b"cybercase")
        == "e14b05e9e196e050aa4e32c66228bd91b2d9e9983550b2b0466fcc98228e6615"
    )


def test_case_fact_pack_rejects_unknown_evidence_ids() -> None:
    with pytest.raises(ValidationError):
        CaseFactPack(
            facts=[
                CaseFact(
                    fact_id="F-001",
                    statement="Unsupported fact",
                    category="case_summary",
                    status="reported",
                    confidence="medium",
                    evidence_ids=["E-999"],
                )
            ],
            evidence_registry=[
                EvidenceReference(
                    evidence_id="E-001",
                    source_type="user_input",
                    source_name="Case text",
                )
            ],
            indicators=[],
            timeline=[],
            mitre_assessments=[],
            legal_assessments=[],
            missing_information=[],
            limitations=[],
            completeness_percentage=20,
            completeness=_completeness(),
            review_status="draft",
        )


def test_legal_assessment_requires_disclaimer() -> None:
    with pytest.raises(ValidationError):
        LegalRelevanceAssessment(
            enabled=True,
            provision_reference="Unknown",
            preliminary_relevance="Needs review",
            status="unknown",
            evidence_ids=["E-001"],
            disclaimer="Missing required wording",
        )


import asyncio

from app.routers import report as report_router
from app.schemas.rag import QueryRequest, ResumeRequest


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeAsyncClient:
    payloads: list[dict[str, object]] = []

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def post(self, url: str, json: dict[str, object]) -> _FakeResponse:
        return _FakeResponse(self.payloads.pop(0))


def test_report_followup_and_resume_flow_use_typed_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeAsyncClient.payloads = [
        {
            "status": "followup",
            "answer": "",
            "followup_question": "Please provide the incident date/time.",
            "session_id": "session-1",
            "missing_information": ["incident date/time"],
        },
        {
            "status": "completed",
            "answer": "report complete",
            "report_id": "report-1",
            "missing_information": [],
        },
    ]
    monkeypatch.setattr(report_router.httpx, "AsyncClient", _FakeAsyncClient)

    started = asyncio.run(report_router.generate_report(QueryRequest(query="short case")))
    assert started.status == "followup"
    assert started.session_id == "session-1"

    resumed = asyncio.run(
        report_router.resume_report(ResumeRequest(session_id="session-1", answer="2026-02-14"))
    )
    assert resumed.status == "completed"
    assert resumed.report_id == "report-1"
