from app.models.case import CaseRecord
from app.services.case_context import CaseContextService


def make_case(data: dict) -> CaseRecord:
    return CaseRecord(
        case_id="CASE-CONTEXT",
        title="  Phishing incident  ",
        status="investigating",
        severity="high",
        data=data,
        case_version=1,
        case_snapshot_hash="",
    )


def test_equivalent_case_context_has_a_stable_hash() -> None:
    first = make_case(
        {
            "incident_summary": "Finance saw a phishing email.\r\n",
            "evidence_items": [
                {"evidence_id": "E-2", "title": "Second"},
                {"evidence_id": "E-1", "title": "First"},
            ],
            "gaps": ["Confirm sender", "Collect headers"],
            "updated_at": "2026-07-10T00:00:00Z",
        }
    )
    second = make_case(
        {
            "incident_summary": "Finance saw a phishing email.\n",
            "evidence_items": [
                {"evidence_id": "E-1", "title": "First"},
                {"evidence_id": "E-2", "title": "Second"},
            ],
            "gaps": ["Collect headers", "Confirm sender"],
            "updated_at": "different and excluded",
        }
    )

    assert CaseContextService.hash_for_case(first) == CaseContextService.hash_for_case(second)


def test_intake_or_evidence_change_creates_a_new_hash() -> None:
    case = make_case({"incident_summary": "Initial narrative", "evidence_items": []})
    initial = CaseContextService.hash_for_case(case)
    case.data = {"incident_summary": "Updated narrative", "evidence_items": []}
    assert CaseContextService.hash_for_case(case) != initial

    case.data = {"incident_summary": "Initial narrative", "evidence_items": [{"evidence_id": "E-1", "title": "Mail header"}]}
    assert CaseContextService.hash_for_case(case) != initial
