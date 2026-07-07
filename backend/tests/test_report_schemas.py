import asyncio
import importlib

import pytest
from pydantic import ValidationError

from app.routers import reports as reports_router
from app.services.report_request_helpers import hash_bytes_sha256
from app.schemas.legacy import legacy_report_response_from_payload
from app.schemas.rag import QueryRequest
from app.schemas.report import (
    CaseFact,
    CaseFactPack,
    CaseInformationCompleteness,
    CompletenessField,
    CyberCaseReport,
    EvidenceReference,
    GenerateReportRequest,
    LegalRelevanceAssessment,
    ReportCompletedResponse,
    ReportFollowUpResponse,
    ReportRequest,
    ReportResumeRequest,
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


def _case_fact_pack() -> CaseFactPack:
    return CaseFactPack(
        facts=[],
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
        missing_information=["incident date/time"],
        limitations=[],
        completeness_percentage=20,
        completeness=_completeness(),
        review_status="draft",
    )


def _report() -> CyberCaseReport:
    case_fact_pack = _case_fact_pack()
    return CyberCaseReport(
        report_id="report-1",
        title="Preliminary report",
        report_type="overview",
        executive_case_summary="Preliminary case summary.",
        case_information_completeness=case_fact_pack.completeness,
        evidence_and_indicators_table=[],
        incident_timeline=[],
        mitre_attack_assessment=[],
        evidence_still_required=case_fact_pack.missing_information,
        investigation_next_steps=["Collect incident date/time."],
        legal_assessments=[],
        limitations_and_disclaimers=[],
        review_status="draft",
        case_fact_pack=case_fact_pack,
        created_at="2026-07-08T00:00:00Z",
    )


def test_sha256_evidence_hashing() -> None:
    assert (
        hash_bytes_sha256(b"cybercase")
        == "e14b05e9e196e050aa4e32c66228bd91b2d9e9983550b2b0466fcc98228e6615"
    )


def test_rag_query_request_has_no_report_only_fields() -> None:
    request = QueryRequest(query="short case")

    assert request.model_dump() == {"query": "short case", "use_agent": True}
    with pytest.raises(ValidationError):
        QueryRequest(query="short case", report_type="overview")


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


def test_canonical_completed_response_excludes_duplicated_top_level_fields() -> None:
    response = ReportCompletedResponse(
        status="completed",
        answer="report complete",
        report_id="report-1",
        report=_report(),
    )

    dumped = response.model_dump(mode="json")

    assert dumped["status"] == "completed"
    assert "case_fact_pack" not in dumped
    assert "completeness" not in dumped
    assert "missing_information" not in dumped
    assert "retrieval_context_id" not in dumped
    assert dumped["report"]["case_fact_pack"]["missing_information"] == [
        "incident date/time"
    ]
from app.schemas.report import ReportErrorResponse

def test_expired_context_returns_error_without_session_id() -> None:
    response = ReportErrorResponse(
        status="context_expired",
        error_code="retrieval_context_expired",
        message="some message"
    )
    dumped = response.model_dump(mode="json")
    assert dumped["status"] == "context_expired"
    assert dumped["error_code"] == "retrieval_context_expired"
    assert "session_id" not in dumped

def test_followup_response_keeps_required_ui_fields() -> None:
    response = ReportFollowUpResponse(
        status="followup",
        followup_question="Please provide the incident date/time.",
        session_id="session-1",
        retrieval_context_id="ctx-1",
        completeness=_completeness(),
        missing_information=["incident date/time"],
    )

    dumped = response.model_dump(mode="json")

    assert dumped["status"] == "followup"
    assert dumped["followup_question"] == "Please provide the incident date/time."
    assert dumped["session_id"] == "session-1"
    assert dumped["completeness"]["percentage"] == 20
    assert dumped["missing_information"] == ["incident date/time"]
    assert "case_fact_pack" not in dumped
    assert "answer" not in dumped


def test_legacy_response_adapter_preserves_old_top_level_fields() -> None:
    legacy = legacy_report_response_from_payload(
        ReportCompletedResponse(
            status="completed",
            answer="report complete",
            report_id="report-1",
            report=_report(),
        )
    )

    assert legacy.status == "completed"
    assert legacy.report_id == "report-1"
    assert legacy.report is not None
    assert legacy.case_fact_pack is not None
    assert legacy.completeness is not None
    assert legacy.missing_information == ["incident date/time"]


class _FakeReportWorkflowService:
    def __init__(self, response: ReportCompletedResponse | ReportFollowUpResponse | ReportErrorResponse):
        self.response = response
        self.requests: list[GenerateReportRequest] = []

    async def generate_report(
        self, *args, **kwargs
    ) -> ReportCompletedResponse | ReportFollowUpResponse | ReportErrorResponse:
        request = args[-1] if args else kwargs.get("request")
        self.requests.append(request)
        return self.response


def test_new_reports_route_uses_canonical_service_response() -> None:
    service = _FakeReportWorkflowService(
        ReportCompletedResponse(
            status="completed",
            answer="report complete",
            report_id="report-1",
            report=_report(),
        )
    )

    result = asyncio.run(
        reports_router.generate_report(
            GenerateReportRequest(query="short case"),
            service=service,  # type: ignore[arg-type]
        )
    )

    assert result.status == "completed"
    assert service.requests[0].query == "short case"
    assert "case_fact_pack" not in result.model_dump(mode="json")
    assert "retrieval_context_id" not in result.model_dump(mode="json")


def test_legacy_report_route_placeholder() -> None:
    pass


def test_new_reports_route_returns_error_response_for_missing_context() -> None:
    service = _FakeReportWorkflowService(
        ReportErrorResponse(
            status="context_expired",
            error_code="retrieval_context_expired",
            message="Context missing"
        )
    )
    result = asyncio.run(
        reports_router.generate_report(
            GenerateReportRequest(query="short case"),
            service=service,  # type: ignore[arg-type]
        )
    )
    dumped = result.model_dump(mode="json")
    assert dumped["status"] == "context_expired"
    assert dumped["error_code"] == "retrieval_context_expired"
    assert "session_id" not in dumped


def test_legacy_report_route_error_placeholder() -> None:
    pass


def test_schema_imports_do_not_create_circular_imports() -> None:
    for module_name in [
        "app.schemas.common",
        "app.schemas.cases",
        "app.schemas.rag",
        "app.schemas.report",
        "app.schemas.legacy",
        "app.routers.rag",
        "app.routers.reports",
    ]:
        assert importlib.import_module(module_name)
