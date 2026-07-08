from __future__ import annotations

import asyncio
import os
from typing import AsyncIterator

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.dependencies import get_report_workflow_service
from app.main import app as backend_app
from app.models.case import CaseRecord
from app.schemas.report import (
    CaseFactPack,
    CaseInformationCompleteness,
    CyberCaseReport,
    MitreAssessment,
)
from app.services.report_workflow import ReportWorkflowService


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/cybercase_framework_test",
)

if not TEST_DATABASE_URL.startswith("postgresql"):
    pytest.skip("Analysis workflow tests require PostgreSQL", allow_module_level=True)

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
def rag_client() -> "_MockRagClient":
    return _MockRagClient()


@pytest.fixture
def report_generator() -> "_MockReportGenerator":
    return _MockReportGenerator()


@pytest.fixture
def client(
    report_generator: "_MockReportGenerator",
    rag_client: "_MockRagClient",
) -> TestClient:
    app = _fastapi_app()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with SessionLocal() as session:
            yield session

    def override_report_service(
        db: AsyncSession = Depends(get_db),
    ) -> ReportWorkflowService:
        return ReportWorkflowService(
            report_gen=report_generator,
            client=rag_client,
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
    def __init__(self) -> None:
        self.query_payloads: list[dict] = []
        self.context_paths: list[str] = []

    async def post_json(self, path: str, payload: dict) -> dict:
        if path == "/query":
            self.query_payloads.append(payload)
            return {"retrieval_context_id": f"ctx-analysis-{len(self.query_payloads)}"}
        return {}

    async def get_json(self, path: str) -> dict:
        self.context_paths.append(path)
        context_id = path.rsplit("/", 1)[-1]
        if context_id == "ctx-expired":
            return {}
        if context_id.startswith("ctx-analysis-"):
            return {
                "retrieval_context_id": context_id,
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
        self.generated_queries: list[str] = []

    def preview_case_fact_pack(
        self,
        query: str,
        legal: bool = False,
        evidence_registry: list | None = None,
    ) -> CaseFactPack:
        self.preview_queries.append(query)
        complete = "Follow-up answer supplied" in query and "unknown" not in query.lower()
        return _case_fact_pack(
            evidence_registry=evidence_registry or [],
            complete=complete,
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
        self.generated_queries.append(query)
        completeness = _completeness(complete=True)
        return CyberCaseReport(
            report_id=f"rep-analysis-{len(self.generated_queries)}",
            title="Analysis Workflow Report",
            report_type=report_type,  # type: ignore[arg-type]
            executive_case_summary="Synthesized analysis workflow report",
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
        return "# Analysis Workflow Report\nRendered markdown preview."


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
    mitre_assessments = []
    if evidence_registry:
        mitre_assessments.append(
            MitreAssessment(
                technique_id="T1566",
                technique_name="Phishing",
                mapping_status="inferred",
                justification="RAG preview candidate.",
                evidence_ids=[evidence_registry[0].evidence_id],
            )
        )
    return CaseFactPack(
        facts=[],
        evidence_registry=evidence_registry,
        indicators=[],
        timeline=[],
        mitre_assessments=mitre_assessments,
        legal_assessments=[],
        missing_information=[] if complete else ["incident date/time"],
        limitations=[],
        completeness_percentage=completeness.percentage,
        completeness=completeness,
        review_status="draft",
    )


def _create_case(client: TestClient, title: str = "Analysis Case") -> str:
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


def _case_data(case_id: str) -> dict:
    async def _load() -> dict:
        async with SessionLocal() as session:
            result = await session.execute(
                select(CaseRecord).where(CaseRecord.case_id == case_id)
            )
            case = result.scalars().first()
            assert case is not None
            return case.data

    return asyncio.run(_load())


def test_start_analysis_creates_session_and_runs_rag(
    client: TestClient,
    rag_client: _MockRagClient,
) -> None:
    case_id = _create_case(client)

    response = client.post(f"/api/v1/cases/{case_id}/analysis/start", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_status"] == "needs_followup"
    assert body["session_id"]
    assert body["retrieval_context_id"] == "ctx-analysis-1"
    assert body["followup_question"]
    assert body["mitre_preview"][0]["technique_id"] == "T1566"
    assert len(rag_client.query_payloads) == 1


def test_get_analysis_returns_cached_session_without_rag(
    client: TestClient,
    rag_client: _MockRagClient,
) -> None:
    case_id = _create_case(client)
    start = client.post(f"/api/v1/cases/{case_id}/analysis/start", json={}).json()

    response = client.get(f"/api/v1/cases/{case_id}/analysis")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_status"] == "needs_followup"
    assert body["session_id"] == start["session_id"]
    assert body["retrieval_context_id"] == "ctx-analysis-1"
    assert len(rag_client.query_payloads) == 1


def test_followup_with_new_facts_updates_case_and_reruns_rag(
    client: TestClient,
    rag_client: _MockRagClient,
) -> None:
    case_id = _create_case(client)
    start = client.post(f"/api/v1/cases/{case_id}/analysis/start", json={}).json()

    response = client.post(
        f"/api/v1/cases/{case_id}/analysis/followup",
        json={
            "session_id": start["session_id"],
            "answer": "The failed logins occurred on 2026-07-07 at 09:30 UTC.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_status"] == "ready_for_report"
    assert body["retrieval_context_id"] == "ctx-analysis-2"
    assert body["followup_question"] is None
    assert len(rag_client.query_payloads) == 2
    answers = _case_data(case_id)["report_followup_answers"]
    assert answers[-1]["answer"] == "The failed logins occurred on 2026-07-07 at 09:30 UTC."


def test_followup_without_new_facts_keeps_cached_context(
    client: TestClient,
    rag_client: _MockRagClient,
) -> None:
    case_id = _create_case(client)
    start = client.post(f"/api/v1/cases/{case_id}/analysis/start", json={}).json()

    response = client.post(
        f"/api/v1/cases/{case_id}/analysis/followup",
        json={"session_id": start["session_id"], "answer": "unknown"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_status"] == "needs_followup"
    assert body["retrieval_context_id"] == "ctx-analysis-1"
    assert len(rag_client.query_payloads) == 1


def test_generate_report_reuses_active_analysis_context(
    client: TestClient,
    rag_client: _MockRagClient,
    report_generator: _MockReportGenerator,
) -> None:
    case_id = _create_case(client)
    start = client.post(f"/api/v1/cases/{case_id}/analysis/start", json={}).json()
    client.post(
        f"/api/v1/cases/{case_id}/analysis/followup",
        json={
            "session_id": start["session_id"],
            "answer": "The failed logins occurred on 2026-07-07 at 09:30 UTC.",
        },
    )

    response = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview", "legal": False, "force_generate": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["retrieval_context_id"] == "ctx-analysis-2"
    assert len(rag_client.query_payloads) == 2
    assert "Previously provided follow-up answers" in report_generator.generated_queries[-1]
    assert "2026-07-07 at 09:30 UTC" in report_generator.generated_queries[-1]
    cached = client.get(f"/api/v1/cases/{case_id}/analysis").json()
    assert cached["workflow_status"] == "report_generated"
    assert cached["retrieval_context_id"] == "ctx-analysis-2"


def test_direct_report_fallback_and_expired_context_wait(
    client: TestClient,
    rag_client: _MockRagClient,
) -> None:
    case_id = _create_case(client)

    direct = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={"report_type": "overview", "legal": False, "force_generate": True},
    )
    assert direct.status_code == 200
    assert direct.json()["status"] == "completed"
    assert direct.json()["retrieval_context_id"] == "ctx-analysis-1"
    assert len(rag_client.query_payloads) == 1

    expired_case_id = _create_case(client, title="Expired Context Case")
    expired = client.post(
        f"/api/v1/cases/{expired_case_id}/report",
        json={
            "report_type": "overview",
            "legal": False,
            "force_generate": True,
            "retrieval_context_id": "ctx-expired",
        },
    )
    assert expired.status_code == 200
    assert expired.json()["status"] == "context_expired"
    assert expired.json()["error_code"] == "retrieval_context_expired"
