import asyncio

import pytest
from fastapi import HTTPException

from app.routers.cases import create_case, get_case, update_case
from app.schemas.cases import CaseCreate, CaseUpdate


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


def test_create_case_returns_stable_case_id() -> None:
    db = _FakeDb()

    created = asyncio.run(create_case(CaseCreate(title="Wire fraud"), db=db))

    assert created.case_id.startswith("CASE-")
    assert created.title == "Wire fraud"
    assert db.added.case_id == created.case_id
    assert db.commits == 1


def test_get_case_returns_full_saved_case() -> None:
    db = _FakeDb()
    created = asyncio.run(create_case(CaseCreate(title="Persisted case"), db=db))

    loaded = asyncio.run(get_case(created.case_id, db=db))

    assert loaded.case_id == created.case_id
    assert loaded.title == "Persisted case"


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


def test_patch_intake_generates_downstream_case_outputs() -> None:
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
    assert updated.gaps
    assert updated.affected_assets
    assert {mapping.technique_id for mapping in updated.attack_mappings} >= {"T1566", "T1114", "T1213"}
    assert db.record.data["attack_mappings"][0]["metadata"]["source_type"] == "system_rule"


def test_get_missing_case_returns_404() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_case("CASE-MISSING", db=_FakeDb(record=None)))

    assert exc_info.value.status_code == 404
