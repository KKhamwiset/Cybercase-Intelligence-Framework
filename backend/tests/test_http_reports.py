from __future__ import annotations

import asyncio
import os
from typing import AsyncIterator

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.pool import NullPool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.dependencies import get_report_workflow_service
from app.main import app as backend_app
from app.models.case import CaseRecord
from app.schemas.report import (
    CaseFactPack,
    CaseInformationCompleteness,
    CyberCaseReport,
)
from app.services.report_workflow import ReportWorkflowService


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/cybercase_framework_test",
)

if not TEST_DATABASE_URL.startswith("postgresql"):
    pytest.skip("HTTP report tests require PostgreSQL", allow_module_level=True)

engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _check_database() -> None:
    async with engine.connect():
        return None


try:
    asyncio.run(_check_database())
except Exception as exc:  # pragma: no cover - environment-specific skip
    pytest.skip(
        f"PostgreSQL test database is unavailable: {exc}",
        allow_module_level=True,
    )


def _fastapi_app():
    return getattr(backend_app, "app", backend_app)


@pytest.fixture(autouse=True)
def reset_database() -> None:
    async def _reset() -> None:
        import app.models  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_reset())


@pytest.fixture
def report_generator() -> "_MockReportGenerator":
    return _MockReportGenerator()


@pytest.fixture
def client(report_generator: "_MockReportGenerator") -> TestClient:
    app = _fastapi_app()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with SessionLocal() as session:
            yield session

    def override_report_service(
        db: AsyncSession = Depends(get_db),
    ) -> ReportWorkflowService:
        return ReportWorkflowService(
            report_gen=report_generator,
            client=_MockRagClient(),
            db=db,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_report_workflow_service] = override_report_service
    try:
        with TestClient(backend_app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


class _MockRagClient:
    async def post_json(self, path: str, payload: dict) -> dict:
        if path == "/query":
            return {"retrieval_context_id": "ctx-http"}
        return {}

    async def get_json(self, path: str) -> dict:
        if path == "/retrieval-contexts/ctx-http":
            return {
                "retrieval_context_id": "ctx-http",
                "query": "Suspicious logins from a foreign IP.",
                "rag_result": {},
                "context": "Sample threat context data",
                "answer": "Sample RAG answer",
                "mitre_table": [],
            }
        return {}


class _MockReportGenerator:
    def __init__(self) -> None:
        self.preview_queries: list[str] = []
        self.generated_reports = 0

    def preview_case_fact_pack(
        self,
        query: str,
        legal: bool = False,
        evidence_registry: list | None = None,
    ) -> CaseFactPack:
        self.preview_queries.append(query)
        has_prior_answer = "Previously provided follow-up answers" in query
        return _case_fact_pack(
            evidence_registry=evidence_registry or [],
            complete=has_prior_answer,
        )

    def generate(
        self,
        query: str,
        context: str,
        rag_result: dict | None = None,
        mitre_table: list | None = None,
        rag_answer: str = "",
        report_type: str = "overview",
        legal: bool = False,
        evidence_registry: list | None = None,
        force_generate: bool = False,
    ) -> CyberCaseReport:
        self.generated_reports += 1
        completeness = _completeness(complete=True)
        return CyberCaseReport(
            report_id=f"rep-http-{self.generated_reports}",
            title="HTTP Incident Report",
            report_type=report_type,  # type: ignore[arg-type]
            executive_case_summary="Synthesized HTTP incident report",
            case_information_completeness=completeness,
            evidence_and_indicators_table=[],
            incident_timeline=[],
            mitre_attack_assessment=[],
            evidence_still_required=[],
            investigation_next_steps=[],
            legal_assessments=[],
            limitations_and_disclaimers=[],
            review_status="draft",
            case_fact_pack=_case_fact_pack(
                evidence_registry=evidence_registry or [],
                complete=True,
            ),
            created_at="2026-07-08T00:00:00Z",
        )

    def render_report_markdown(self, report: CyberCaseReport) -> str:
        return "# HTTP Incident Report\nRendered markdown preview."


def _completeness(complete: bool) -> CaseInformationCompleteness:
    return CaseInformationCompleteness(
        percentage=100 if complete else 20,
        status=(
            "Sufficient for preliminary report"
            if complete
            else "Incomplete - follow-up required"
        ),
        missing_fields=[] if complete else ["incident date/time"],
        fields=[],
    )


def _case_fact_pack(
    *,
    evidence_registry: list,
    complete: bool,
) -> CaseFactPack:
    completeness = _completeness(complete)
    return CaseFactPack(
        facts=[],
        evidence_registry=evidence_registry,
        indicators=[],
        timeline=[],
        mitre_assessments=[],
        legal_assessments=[],
        missing_information=[] if complete else ["incident date/time"],
        limitations=[],
        completeness_percentage=completeness.percentage,
        completeness=completeness,
        review_status="draft",
    )


def _create_case(client: TestClient, title: str = "HTTP Case") -> str:
    response = client.post(
        "/api/v1/cases",
        json={
            "title": title,
            "severity": "high",
            "incident_summary": "Suspicious logins from a foreign IP.",
        },
    )
    assert response.status_code == 201
    return response.json()["case_id"]


def test_case_owned_report_accepts_body_without_query(
    client: TestClient,
    report_generator: _MockReportGenerator,
) -> None:
    case_id = _create_case(client)

    response = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview", "legal": False, "force_generate": True},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert report_generator.preview_queries[0].startswith("Suspicious logins")


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/reports/generate",
        "/api/v1/reports/generate-file",
        "/api/v1/reports/resume",
        "/api/v1/rag/generate-report",
    ],
)
def test_legacy_report_endpoints_are_gone(client: TestClient, path: str) -> None:
    response = client.post(path, json={})
    assert response.status_code in {404, 405}


def test_report_registry_get_and_review_status(client: TestClient) -> None:
    case_id = _create_case(client)
    generated = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview", "force_generate": True},
    )
    assert generated.status_code == 200
    report_id = generated.json()["report_id"]

    listing = client.get("/api/v1/reports")
    assert listing.status_code == 200
    assert listing.json()[0]["report_id"] == report_id

    detail = client.get(f"/api/v1/reports/{report_id}")
    assert detail.status_code == 200
    assert detail.json()["report"]["report_id"] == report_id

    updated = client.patch(
        f"/api/v1/reports/{report_id}/review-status",
        json={"review_status": "approved"},
    )
    assert updated.status_code == 200
    assert updated.json()["report"]["review_status"] == "approved"


def test_followup_wrong_case_is_forbidden(client: TestClient) -> None:
    first_case_id = _create_case(client, "First case")
    second_case_id = _create_case(client, "Second case")

    followup = client.post(
        f"/api/v1/cases/{first_case_id}/report",
        json={"report_type": "overview"},
    )
    assert followup.status_code == 200
    assert followup.json()["status"] == "followup"

    forbidden = client.post(
        f"/api/v1/cases/{second_case_id}/report/resume",
        json={"session_id": followup.json()["session_id"], "answer": "10:00 UTC"},
    )
    assert forbidden.status_code == 403


def test_followup_answer_persists_and_regenerate_does_not_repeat_question(
    client: TestClient,
    report_generator: _MockReportGenerator,
) -> None:
    case_id = _create_case(client)

    followup = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview"},
    )
    assert followup.status_code == 200
    assert followup.json()["status"] == "followup"
    question = followup.json()["followup_question"]

    resumed = client.post(
        f"/api/v1/cases/{case_id}/report/resume",
        json={"session_id": followup.json()["session_id"], "answer": "10:00 UTC"},
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "completed"

    async def _load_case_data() -> dict:
        async with SessionLocal() as session:
            result = await session.execute(
                select(CaseRecord).where(CaseRecord.case_id == case_id)
            )
            case = result.scalars().first()
            assert case is not None
            return case.data

    case_data = asyncio.run(_load_case_data())
    answers = case_data["report_followup_answers"]
    assert answers == [
        {
            "question": question,
            "answer": "10:00 UTC",
            "answered_at": answers[0]["answered_at"],
            "source": "report_followup",
        }
    ]

    regenerated = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview"},
    )
    assert regenerated.status_code == 200
    assert regenerated.json()["status"] == "completed"
    assert "Previously provided follow-up answers" in report_generator.preview_queries[-1]
    assert "10:00 UTC" in report_generator.preview_queries[-1]
