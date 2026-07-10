import asyncio

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.sql.dml import Delete

from app.routers.cases import create_case, delete_case, get_case, list_cases, update_case
from app.models.case_chat import CaseChatState
from app.models.report import ReportSessionRecord
from app.schemas.cases import CaseCreate, CaseUpdate
from app.services.case_context import CaseContextService


class _FakeDb:
    def __init__(self, record=None) -> None:
        self.record = record
        self.added = None
        self.commits = 0

    def add(self, record) -> None:
        self.added = record
        self.record = record

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, record) -> None:
        if getattr(record, "created_at", None) is None:
            record.created_at = None
        if getattr(record, "updated_at", None) is None:
            record.updated_at = None

    async def execute(self, statement):
        if isinstance(statement, Delete):
            self.record = None
            return _Result(None)
        return _Result(self.record)


class _Result:
    def __init__(self, record) -> None:
        self.record = record

    def scalars(self):
        return _Scalars(self.record)


class _Scalars:
    def __init__(self, record) -> None:
        self.record = record

    def first(self):
        return self.record

    def all(self):
        return [self.record] if self.record is not None else []


class _DeleteConflictDb:
    def __init__(self, case, *, state=None, session=None) -> None:
        self.case = case
        self.state = state
        self.session = session

    async def execute(self, statement):
        if isinstance(statement, Delete):
            raise AssertionError("conflicted delete must not execute")
        entity = statement.column_descriptions[0]["entity"]
        if entity is type(self.case):
            return _Result(self.case)
        if entity is CaseChatState:
            return _Result(self.state)
        if entity is ReportSessionRecord:
            return _Result(self.session)
        return _Result(None)

    async def commit(self) -> None:
        raise AssertionError("conflicted delete must not commit")


def test_create_case_returns_stable_case_id() -> None:
    db = _FakeDb()

    created = asyncio.run(create_case(CaseCreate(title="Wire fraud"), db=db))

    assert created.case_id.startswith("CASE-")
    assert created.title == "Wire fraud"
    assert created.case_version == 1
    assert "case_version" not in db.added.data
    assert db.added.case_id == created.case_id
    assert db.commits == 1


def test_create_preserves_explicit_analyst_evidence() -> None:
    db = _FakeDb()
    created = asyncio.run(
        create_case(
            CaseCreate(
                title="Evidence case",
                incident_summary="A phishing message was reported.",
                evidence_items=[
                    {
                        "evidence_id": "ANALYST-1",
                        "title": "Original message",
                        "description": "Collected by the analyst",
                        "source_type": "analyst_input",
                    }
                ],
            ),
            db=db,
        )
    )

    assert [item.evidence_id for item in created.evidence_items] == ["ANALYST-1"]
    assert created.evidence_items[0].intake_derived is False


def test_get_case_returns_full_saved_case() -> None:
    db = _FakeDb()
    created = asyncio.run(create_case(CaseCreate(title="Persisted case"), db=db))

    loaded = asyncio.run(get_case(created.case_id, db=db))

    assert loaded.case_id == created.case_id
    assert loaded.title == "Persisted case"


def test_list_cases_exposes_authoritative_case_version() -> None:
    db = _FakeDb()
    created = asyncio.run(create_case(CaseCreate(title="Listed case"), db=db))

    listed = asyncio.run(list_cases(db=db))

    assert [(item.case_id, item.case_version) for item in listed] == [
        (created.case_id, 1)
    ]


def test_patch_case_safely_updates_one_section() -> None:
    db = _FakeDb()
    created = asyncio.run(create_case(CaseCreate(title="Partial update"), db=db))

    updated = asyncio.run(
        update_case(
            created.case_id,
            CaseUpdate(incident_summary="Saved intake narrative"),
            db=db,
        )
    )

    assert updated.title == "Partial update"
    assert updated.incident_summary == "Saved intake narrative"
    assert db.record.data["incident_summary"] == "Saved intake narrative"


def test_patch_intake_keeps_generated_gaps_and_recommendations_empty() -> None:
    db = _FakeDb()
    created = asyncio.run(create_case(CaseCreate(title="Phishing case"), db=db))

    narrative = """
    On 18 June 2026 at 09:14, a Finance employee received a phishing email
    and entered credentials into a fake Microsoft 365 login page. The attacker
    used repeated MFA push notifications, created an inbox rule named RSS Feeds,
    searched the mailbox, and downloaded files from SharePoint.

    ## Available Evidence
    * Original phishing email
    * Microsoft 365 sign-in from unusual foreign IP address
    * Newly created inbox rule named RSS Feeds
    * SharePoint audit logs showing downloads
    """

    updated = asyncio.run(
        update_case(
            created.case_id,
            CaseUpdate(incident_summary=narrative),
            db=db,
        )
    )

    assert updated.evidence_items
    assert updated.gaps == []
    assert updated.recommendations == []
    assert updated.affected_assets
    assert {mapping.technique_id for mapping in updated.attack_mappings} >= {"T1566", "T1114", "T1213"}
    assert db.record.data["attack_mappings"][0]["metadata"]["source_type"] == "system_rule"
    assert all(item.source_type == "analyst_input" for item in updated.evidence_items)
    assert all(item.intake_derived for item in updated.evidence_items)


def test_replacing_intake_replaces_all_prior_deterministic_derivations() -> None:
    old_narrative = (
        "At 09:14 a Finance employee received a phishing email, entered credentials "
        "into a fake Microsoft 365 login page, and files were downloaded from SharePoint."
    )
    new_narrative = (
        "At 10:15 an employee received repeated MFA push notifications. "
        "The account was disabled and a password reset was completed."
    )
    db = _FakeDb()
    created = asyncio.run(
        create_case(
            CaseCreate(title="Replace intake", incident_summary=old_narrative), db=db
        )
    )
    assert {item.technique_id for item in created.attack_mappings} >= {"T1566", "T1213"}

    updated = asyncio.run(
        update_case(
            created.case_id,
            CaseUpdate(incident_summary=new_narrative),
            db=db,
        )
    )

    assert {item.technique_id for item in updated.attack_mappings} == {"T1621"}
    assert all("phishing" not in item.description.lower() for item in updated.evidence_items)
    assert [item.title for item in updated.timeline_events] == ["10:15 event"]
    assert {item.title for item in updated.containment_actions} == {
        "Disable compromised account",
        "Reset account password",
    }
    assert "Finance department employee account" not in updated.affected_users
    assert "Finance SharePoint folder" not in updated.affected_assets


def test_clearing_intake_removes_prior_deterministic_derivations() -> None:
    db = _FakeDb()
    created = asyncio.run(
        create_case(
            CaseCreate(
                title="Clear intake",
                incident_summary=(
                    "At 09:14 a Finance employee received a phishing email in Microsoft 365, "
                    "downloaded SharePoint files, and the account was disabled."
                ),
            ),
            db=db,
        )
    )
    assert created.evidence_items and created.attack_mappings

    updated = asyncio.run(
        update_case(created.case_id, CaseUpdate(incident_summary=""), db=db)
    )

    assert updated.incident_summary == ""
    assert updated.evidence_items == []
    assert updated.timeline_events == []
    assert updated.attack_mappings == []
    assert updated.containment_actions == []
    assert updated.affected_users == []
    assert updated.affected_assets == []


def test_replacing_intake_preserves_mixed_analyst_owned_items() -> None:
    db = _FakeDb()
    created = asyncio.run(
        create_case(
            CaseCreate(
                title="Mixed intake",
                incident_summary=(
                    "At 09:14 a Finance employee received a phishing email in Microsoft 365 "
                    "and downloaded SharePoint files."
                ),
            ),
            db=db,
        )
    )
    payload = dict(db.record.data)
    payload["evidence_items"] = [
        *payload["evidence_items"],
        {
            "evidence_id": "MANUAL-E",
            "title": "Preserved identity log",
            "description": "Collected separately by the analyst.",
            "source_type": "log",
            "status": "unknown",
            "confidence": "low",
            "analyst_verified": False,
        },
    ]
    payload["timeline_events"] = [
        *payload["timeline_events"],
        {
            "event_id": "MANUAL-TL",
            "title": "Analyst-confirmed event",
            "description": "Preserve this event.",
            "metadata": {"source_type": "analyst_input"},
        },
    ]
    payload["containment_actions"] = [
        *payload["containment_actions"],
        {
            "action_id": "MANUAL-ACT",
            "title": "Analyst containment",
            "description": "Preserve this action.",
            "metadata": {"source_type": "analyst_input"},
        },
    ]
    payload["affected_users"] = [*payload["affected_users"], "Manual user"]
    payload["affected_assets"] = [*payload["affected_assets"], "Manual asset"]
    db.record.data = payload
    db.record.case_snapshot_hash = CaseContextService.hash_for_case(db.record)

    updated = asyncio.run(
        update_case(
            created.case_id,
            CaseUpdate(
                incident_summary="At 11:20 repeated MFA push notifications were reported."
            ),
            db=db,
        )
    )

    assert "MANUAL-E" in {item.evidence_id for item in updated.evidence_items}
    assert "MANUAL-TL" in {item.event_id for item in updated.timeline_events}
    assert "MANUAL-ACT" in {item.action_id for item in updated.containment_actions}
    assert "Manual user" in updated.affected_users
    assert "Manual asset" in updated.affected_assets
    assert {item.technique_id for item in updated.attack_mappings} == {"T1621"}


def test_patch_rejects_unknown_and_generated_fields() -> None:
    with pytest.raises(ValidationError):
        CaseUpdate.model_validate({"case_id": "CASE-IMMUTABLE"})
    with pytest.raises(ValidationError):
        CaseUpdate.model_validate({"recommendations": []})
    with pytest.raises(ValidationError):
        CaseUpdate.model_validate({"unexpected": "value"})
    with pytest.raises(ValidationError):
        CaseUpdate.model_validate({"title": None})


def test_create_rejects_immutable_unknown_and_invalid_nested_provenance() -> None:
    with pytest.raises(ValidationError):
        CaseCreate.model_validate({"case_id": "CASE-CLIENT-OWNED", "title": "Invalid"})
    with pytest.raises(ValidationError):
        CaseCreate.model_validate({"title": "   "})
    with pytest.raises(ValidationError):
        CaseCreate.model_validate(
            {
                "title": "Invalid provenance",
                "evidence_items": [
                    {
                        "evidence_id": "RAG-1",
                        "title": "Claimed model output",
                        "source_type": "rag",
                    }
                ],
            }
        )


def test_patch_normalized_noop_does_not_increment_case_version() -> None:
    db = _FakeDb()
    created = asyncio.run(create_case(CaseCreate(title="Normalized title"), db=db))

    updated = asyncio.run(
        update_case(created.case_id, CaseUpdate(title="  Normalized title  "), db=db)
    )

    assert updated.case_version == 1
    assert db.record.case_version == 1


def test_patch_analysis_relevant_input_increments_case_version() -> None:
    db = _FakeDb()
    created = asyncio.run(create_case(CaseCreate(title="Versioned case"), db=db))

    updated = asyncio.run(
        update_case(
            created.case_id,
            CaseUpdate(analyst_notes="Confirmed by the assigned analyst."),
            db=db,
        )
    )

    assert updated.case_version == 2
    assert db.record.case_version == 2


def test_delete_case_hard_deletes_record() -> None:
    db = _FakeDb()
    created = asyncio.run(create_case(CaseCreate(title="Disposable"), db=db))

    response = asyncio.run(delete_case(created.case_id, db=db))

    assert response.status_code == 204
    assert db.record is None


def test_delete_case_rejects_pending_analysis() -> None:
    case = _FakeDb()
    created = asyncio.run(create_case(CaseCreate(title="Pending case"), db=case))
    state = CaseChatState(
        case_id=created.case_id,
        case_version=1,
        case_snapshot_hash=case.record.case_snapshot_hash,
        status="pending",
    )
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(delete_case(created.case_id, db=_DeleteConflictDb(case.record, state=state)))
    assert exc_info.value.status_code == 409


def test_delete_case_rejects_pending_report_followup() -> None:
    case = _FakeDb()
    created = asyncio.run(create_case(CaseCreate(title="Follow-up case"), db=case))
    session = ReportSessionRecord(
        session_id="REPORT-SESSION",
        case_id=created.case_id,
        request_payload_json={},
        followup_question="When did the incident occur?",
    )
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            delete_case(created.case_id, db=_DeleteConflictDb(case.record, session=session))
        )
    assert exc_info.value.status_code == 409


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_missing_case_mutations_return_404(operation: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        if operation == "update":
            asyncio.run(update_case("CASE-MISSING", CaseUpdate(title="Missing"), db=_FakeDb()))
        else:
            asyncio.run(delete_case("CASE-MISSING", db=_FakeDb()))
    assert exc_info.value.status_code == 404


def test_get_missing_case_returns_404() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_case("CASE-MISSING", db=_FakeDb(record=None)))

    assert exc_info.value.status_code == 404
