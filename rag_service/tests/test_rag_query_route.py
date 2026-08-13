from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from routers import rag as rag_router
from schemas.rag import QueryResponse


class FakeRagAgent:
    def __init__(self) -> None:
        self.query_calls: list[tuple[str, bool]] = []
        self.retrieve_with_details_calls = 0

    def query(self, query: str, *, verbose: bool) -> SimpleNamespace:
        self.query_calls.append((query, verbose))
        return SimpleNamespace(
            answer="SENTINEL_THROWAWAY_ANSWER",
            context="retrieved MITRE context",
            graphrag_result={"sentinel": "raw retrieval"},
        )

    def retrieve_with_details(self, query: str) -> None:
        self.retrieve_with_details_calls += 1
        raise AssertionError(f"direct retrieval called for {query}")


def test_query_runs_full_agent_pipeline_without_exposing_generated_answer(
    monkeypatch,
) -> None:
    app = FastAPI()
    agent = FakeRagAgent()
    app.state.rag_agent = agent
    app.state.retrieval_contexts = {}
    app.include_router(rag_router.router)
    builder_calls: list[tuple[object, str]] = []

    def build_table(result: object, answer: str) -> list[object]:
        builder_calls.append((result, answer))
        return []

    monkeypatch.setattr(rag_router, "build_mitre_table", build_table)

    response = TestClient(app).post("/query", json={"query": "incident summary"})

    assert response.status_code == 200
    assert agent.query_calls == [("incident summary", False)]
    assert agent.retrieve_with_details_calls == 0
    assert builder_calls == [
        ({"sentinel": "raw retrieval"}, "SENTINEL_THROWAWAY_ANSWER")
    ]

    payload = response.json()
    assert payload == {
        "status": "completed",
        "retrieval_context_id": payload["retrieval_context_id"],
        "context": "retrieved MITRE context",
        "mitre_table": [],
    }
    assert payload["retrieval_context_id"]
    assert "SENTINEL_THROWAWAY_ANSWER" not in response.text

    with pytest.raises(ValidationError):
        QueryResponse.model_validate({**payload, "answer": "forbidden"})

    cached = app.state.retrieval_contexts[payload["retrieval_context_id"]]
    assert cached["context"] == "retrieved MITRE context"
    assert cached["rag_result"] == {"sentinel": "raw retrieval"}
    assert cached["mitre_table"] == []
    assert "answer" not in cached
