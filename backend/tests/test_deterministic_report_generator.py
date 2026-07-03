import asyncio

import pytest
from fastapi import HTTPException

from app.routers.cases import get_case_report
from app.schemas.report import StructuredCase
from app.services.report_generator import DeterministicReportGenerator


def _complete_case() -> StructuredCase:
    return StructuredCase(
        case_id="CASE-001",
        title="Phishing credential theft",
        case_type="incident",
        status="contained",
        severity="high",
        incident_summary="A finance employee submitted credentials to a phishing site.",
        affected_users=["finance.user@example.com"],
        affected_assets=["Corporate email account", "Online banking account"],
        evidence_items=[
            {
                "evidence_id": "E-001",
                "title": "Proxy log",
                "description": "Proxy log shows access to the phishing domain.",
                "source_type": "log",
                "status": "confirmed",
                "confidence": "high",
                "analyst_verified": True,
            }
        ],
        timeline_events=[
            {
                "event_id": "T-002",
                "timestamp": "2026-02-14T09:25:00Z",
                "title": "Credentials submitted",
                "metadata": {
                    "status": "confirmed",
                    "confidence": "high",
                    "evidence_ids": ["E-001"],
                    "source_type": "log",
                    "analyst_verified": True,
                },
            },
            {
                "event_id": "T-001",
                "timestamp": "2026-02-14T09:20:00Z",
                "title": "Phishing link opened",
                "metadata": {
                    "status": "confirmed",
                    "confidence": "high",
                    "evidence_ids": ["E-001"],
                    "source_type": "log",
                    "analyst_verified": True,
                },
            },
        ],
        attack_mappings=[
            {
                "mapping_id": "M-001",
                "technique_id": "T1566",
                "technique_name": "Phishing",
                "tactic": "Initial Access",
                "rationale": "The case evidence shows a phishing link used to capture credentials.",
                "metadata": {
                    "status": "confirmed",
                    "confidence": "high",
                    "evidence_ids": ["E-001"],
                    "source_type": "analyst_input",
                    "analyst_verified": True,
                },
            }
        ],
        containment_actions=[
            {
                "action_id": "C-001",
                "title": "Reset affected account password",
                "status": "confirmed",
                "metadata": {
                    "status": "confirmed",
                    "confidence": "high",
                    "evidence_ids": ["E-001"],
                    "source_type": "analyst_input",
                    "analyst_verified": True,
                },
            }
        ],
        recommendations=[
            {
                "action_id": "R-001",
                "title": "Review mail gateway controls",
                "status": "confirmed",
                "metadata": {
                    "status": "confirmed",
                    "confidence": "medium",
                    "evidence_ids": ["E-001"],
                    "source_type": "analyst_input",
                    "analyst_verified": True,
                },
            }
        ],
    )


def _section(report, section_id: str):
    return next(section for section in report.sections if section.id == section_id)


def test_complete_case_produces_expected_sections() -> None:
    report = DeterministicReportGenerator().generate(_complete_case())

    assert report.report_status == "ready_for_review"
    assert [section.id for section in report.sections] == [
        "executive_summary",
        "incident_overview",
        "scope_and_affected_assets",
        "attack_timeline",
        "mitre_attack_mapping",
        "evidence_register",
        "containment_and_response_actions",
        "recommendations",
        "evidence_gaps_and_limitations",
    ]
    assert report.gaps == []


def test_missing_timeline_produces_visible_gap() -> None:
    case = _complete_case().model_copy(update={"timeline_events": []})
    report = DeterministicReportGenerator().generate(case)

    assert report.report_status == "incomplete"
    assert any(gap.gap_id == "gap_timeline" for gap in report.gaps)
    assert _section(report, "attack_timeline").status == "missing"


def test_attack_mapping_without_evidence_is_candidate_and_incomplete() -> None:
    case = _complete_case()
    case.attack_mappings[0].metadata.evidence_ids = []
    case.attack_mappings[0].metadata.status = "confirmed"
    report = DeterministicReportGenerator().generate(case)
    mapping = _section(report, "mitre_attack_mapping").content["tactics"][0]["mappings"][0]

    assert mapping["status"] == "candidate"
    assert any(gap.gap_id == "gap_mapping_M-001" for gap in report.gaps)


def test_confirmed_rag_mapping_without_analyst_evidence_is_not_confirmed() -> None:
    case = _complete_case()
    case.attack_mappings[0].metadata.source_type = "rag"
    case.attack_mappings[0].metadata.analyst_verified = False
    report = DeterministicReportGenerator().generate(case)
    mapping = _section(report, "mitre_attack_mapping").content["tactics"][0]["mappings"][0]

    assert mapping["status"] == "candidate"
    assert report.report_status == "draft"


def test_timeline_events_are_ordered_chronologically() -> None:
    report = DeterministicReportGenerator().generate(_complete_case())
    timeline = _section(report, "attack_timeline").content["events"]

    assert [event["event_id"] for event in timeline] == ["T-001", "T-002"]


class _EmptyScalars:
    def first(self):
        return None


class _EmptyResult:
    def scalars(self):
        return _EmptyScalars()


class _EmptyDb:
    async def execute(self, statement):
        return _EmptyResult()


def test_invalid_case_id_returns_404() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_case_report("missing-case", db=_EmptyDb()))

    assert exc_info.value.status_code == 404
