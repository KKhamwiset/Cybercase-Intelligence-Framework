import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

# Add the current directory to sys.path so we can import RAG.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from RAG import (  # noqa: E402
    AgentResponse,
    CyberCaseReport,
    EvidenceReference,
    GraphRAGAgent,
    GraphRAGChain,
    HybridRetriever,
    ReportGenerator,
    ReportWorkflowResponse,
    build_context,
    build_retrieval_queries,
)
from RAG.GraphRAG.pipeline.thanoy_client import get_legal_advice  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    print("[RAG Service] Initializing RAG modules...")
    app.state.report_store = {}
    app.state.report_sessions = {}
    app.state.retrieval_contexts = {}
    use_local = False

    try:
        from FlagEmbedding import BGEM3FlagModel
        from RAG.GraphRAG.config import EMBED_MODEL, USE_FP16, USE_LOCAL

        use_local = USE_LOCAL
        print(f"[RAG Service] Loading shared embedding model: {EMBED_MODEL}")
        embed_model = BGEM3FlagModel(EMBED_MODEL, use_fp16=USE_FP16)

        print(
            f"[RAG Service] LLM mode: {'LOCAL (Ollama)' if use_local else 'CLOUD (Claude)'}"
        )
        app.state.rag_chain = GraphRAGChain(embed_model=embed_model, use_local=use_local)
        app.state.rag_agent = GraphRAGAgent(embed_model=embed_model, use_local=use_local)
        app.state.retriever = HybridRetriever(embed_model=embed_model)
        app.state.report_gen = ReportGenerator(use_local=use_local)
        print("[RAG Service] RAG modules initialized successfully.")
    except Exception as e:
        print(f"[RAG Service] Error initializing RAG modules: {e}")
        import traceback

        traceback.print_exc()
        app.state.rag_chain = None
        app.state.rag_agent = None
        app.state.retriever = None
        app.state.report_gen = ReportGenerator(use_local=use_local)

    yield

    if app.state.rag_chain:
        app.state.rag_chain.close()
    if app.state.rag_agent:
        app.state.rag_agent.close()
    if app.state.retriever:
        app.state.retriever.close()
    print("[RAG Service] RAG modules shut down.")


app = FastAPI(title="Cybercase RAG Service", lifespan=lifespan)


class QueryRequest(BaseModel):
    query: str
    use_agent: bool = True
    report_type: str = "overview"
    legal: bool = False
    force_generate: bool = False
    evidence_registry: list[EvidenceReference] = Field(default_factory=list)
    retrieval_context_id: str = ""


class QueryResponse(BaseModel):
    status: str
    answer: str = ""
    followup_question: str = ""
    session_id: str = ""
    retrieval_context_id: str = ""


class ResumeRequest(BaseModel):
    session_id: str
    answer: str


class ReviewStatusRequest(BaseModel):
    review_status: Literal["draft", "ai_generated", "reviewed", "approved"]


RETRIEVAL_CONTEXT_TTL_SECONDS = 60 * 60


def _get_retrieval_contexts(req: Request) -> dict[str, dict[str, Any]]:
    contexts = getattr(req.app.state, "retrieval_contexts", None)
    if contexts is None:
        contexts = {}
        req.app.state.retrieval_contexts = contexts
    return contexts


def _prune_retrieval_contexts(req: Request) -> None:
    contexts = _get_retrieval_contexts(req)
    now = time.time()
    expired_ids = [
        context_id
        for context_id, cached in contexts.items()
        if cached.get("expires_at", 0) <= now
    ]
    for context_id in expired_ids:
        contexts.pop(context_id, None)


def _store_retrieval_context(
    req: Request,
    *,
    query: str,
    context: str,
    rag_result: Any,
) -> str:
    if not context or rag_result is None:
        return ""

    _prune_retrieval_contexts(req)
    context_id = str(uuid.uuid4())
    now = time.time()
    _get_retrieval_contexts(req)[context_id] = {
        "query": query,
        "context": context,
        "rag_result": rag_result,
        "created_at": now,
        "expires_at": now + RETRIEVAL_CONTEXT_TTL_SECONDS,
    }
    return context_id


def _load_retrieval_context(req: Request, context_id: str) -> dict[str, Any] | None:
    if not context_id:
        return None

    _prune_retrieval_contexts(req)
    cached = _get_retrieval_contexts(req).get(context_id)
    if cached:
        cached["expires_at"] = time.time() + RETRIEVAL_CONTEXT_TTL_SECONDS
    return cached


@app.get("/health")
async def health(request: Request):
    return {
        "status": "ok",
        "rag_chain": request.app.state.rag_chain is not None,
        "rag_agent": request.app.state.rag_agent is not None,
    }


@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest, req: Request):
    rag_agent = req.app.state.rag_agent
    rag_chain = req.app.state.rag_chain

    if request.use_agent:
        print("Agent requested")
        if not rag_agent:
            raise HTTPException(status_code=503, detail="RAG Agent not available")
        try:
            response: AgentResponse = rag_agent.query(request.query)
            retrieval_context_id = _store_retrieval_context(
                req,
                query=request.query,
                context=response.context,
                rag_result=response.graphrag_result,
            )
            return QueryResponse(
                status=response.status,
                answer=response.answer,
                followup_question=response.followup_question,
                session_id=response.session_id,
                retrieval_context_id=retrieval_context_id,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    if not rag_chain:
        raise HTTPException(status_code=503, detail="RAG Chain not available")
    try:
        answer = rag_chain.query(request.query)
        return QueryResponse(status="completed", answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/resume", response_model=QueryResponse)
async def resume_agent(request: ResumeRequest, req: Request):
    rag_agent = req.app.state.rag_agent
    if not rag_agent:
        raise HTTPException(status_code=503, detail="RAG Agent not available")
    try:
        response: AgentResponse = rag_agent.resume(request.session_id, request.answer)
        retrieval_context_id = _store_retrieval_context(
            req,
            query=request.answer,
            context=response.context,
            rag_result=response.graphrag_result,
        )
        return QueryResponse(
            status=response.status,
            answer=response.answer,
            followup_question=response.followup_question,
            session_id=response.session_id,
            retrieval_context_id=retrieval_context_id,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-report", response_model=ReportWorkflowResponse)
async def generate_report(request: QueryRequest, req: Request):
    report_gen: ReportGenerator | None = req.app.state.report_gen
    if not report_gen:
        raise HTTPException(status_code=503, detail="Report Generator not available")

    preview_pack = report_gen.preview_case_fact_pack(
        request.query,
        legal=request.legal,
        evidence_registry=request.evidence_registry,
    )
    if _needs_report_followup(preview_pack) and not request.force_generate:
        return _start_report_followup(request, req, preview_pack)

    return await _complete_report_generation(request, req)


@app.post("/resume-report", response_model=ReportWorkflowResponse)
async def resume_report(request: ResumeRequest, req: Request):
    report_sessions: dict = req.app.state.report_sessions
    pending = report_sessions.pop(request.session_id, None)
    if not pending:
        raise HTTPException(status_code=404, detail="Report session not found")

    if pending.get("agent_backed"):
        rag_agent = req.app.state.rag_agent
        if rag_agent:
            try:
                rag_agent.resume(request.session_id, request.answer, verbose=False)
            except KeyError:
                pass

    original = QueryRequest.model_validate(pending["request"])
    combined_query = original.query
    if request.answer.strip():
        combined_query = (
            f"{original.query}\n\n"
            "Follow-up answer supplied for preliminary report:\n"
            f"{request.answer.strip()}"
        )
    update_fields = {"query": combined_query, "force_generate": True}
    if request.answer.strip():
        update_fields["retrieval_context_id"] = ""
    resumed_request = original.model_copy(update=update_fields)
    return await _complete_report_generation(resumed_request, req)


@app.get("/reports/{report_id}", response_model=ReportWorkflowResponse)
async def get_report(report_id: str, req: Request):
    report = _get_stored_report(report_id, req)
    report_gen: ReportGenerator | None = req.app.state.report_gen
    answer = report_gen.render_report_markdown(report) if report_gen else report.case_summary
    return ReportWorkflowResponse(
        status="completed",
        answer=answer,
        report_id=report.report_id,
        report=report,
        case_fact_pack=report.case_fact_pack,
        completeness=report.case_information_completeness,
        missing_information=report.case_fact_pack.missing_information,
    )


@app.patch("/reports/{report_id}/review-status", response_model=ReportWorkflowResponse)
async def update_report_review_status(
    report_id: str, request: ReviewStatusRequest, req: Request
):
    report = _get_stored_report(report_id, req)
    report.review_status = request.review_status
    report.case_fact_pack.review_status = request.review_status
    req.app.state.report_store[report_id] = report
    report_gen: ReportGenerator | None = req.app.state.report_gen
    answer = report_gen.render_report_markdown(report) if report_gen else report.case_summary
    return ReportWorkflowResponse(
        status="completed",
        answer=answer,
        report_id=report.report_id,
        report=report,
        case_fact_pack=report.case_fact_pack,
        completeness=report.case_information_completeness,
        missing_information=report.case_fact_pack.missing_information,
    )


async def _complete_report_generation(
    request: QueryRequest, req: Request
) -> ReportWorkflowResponse:
    retriever = req.app.state.retriever
    report_gen: ReportGenerator | None = req.app.state.report_gen

    if not retriever or not report_gen:
        raise HTTPException(
            status_code=503, detail="Report Generator or Retriever not available"
        )

    try:
        print(f"[REPORT] Generating report for: {request.query[:50]}...")
        cached_context = _load_retrieval_context(req, request.retrieval_context_id)
        if cached_context:
            print(f"[REPORT] Reusing retrieval context: {request.retrieval_context_id}")
            rag_result = cached_context["rag_result"]
            context = cached_context["context"]
            retrieval_context_id = request.retrieval_context_id
        else:
            rag_chain = req.app.state.rag_chain
            english_query = (
                rag_chain.translator.translate_query(request.query)
                if rag_chain
                else request.query
            )
            queries = build_retrieval_queries(request.query, english_query)
            rag_result = retriever.retrieve_multi(queries)
            context = build_context(rag_result)
            retrieval_context_id = _store_retrieval_context(
                req,
                query=request.query,
                context=context,
                rag_result=rag_result,
            )

        report = report_gen.generate(
            request.query,
            context,
            rag_result=rag_result,
            report_type=request.report_type,
            legal=request.legal,
            evidence_registry=request.evidence_registry,
            force_generate=request.force_generate,
        )
        if request.legal:
            await _apply_thanoy_legal_advice(report)

        req.app.state.report_store[report.report_id] = report
        return ReportWorkflowResponse(
            status="completed",
            answer=report_gen.render_report_markdown(report),
            report_id=report.report_id,
            report=report,
            case_fact_pack=report.case_fact_pack,
            completeness=report.case_information_completeness,
            missing_information=report.case_fact_pack.missing_information,
            retrieval_context_id=retrieval_context_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        print(f"[REPORT] Error: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


async def _apply_thanoy_legal_advice(report: CyberCaseReport) -> None:
    advice = await get_legal_advice(report.executive_case_summary or report.case_summary)
    if not advice:
        return

    registry = report.case_fact_pack.evidence_registry
    legal_evidence_id = _next_report_evidence_id(registry)
    registry.append(
        EvidenceReference(
            evidence_id=legal_evidence_id,
            source_type="legal_source",
            source_name="Thanoy legal AI response",
            excerpt=advice[:1200],
        )
    )

    existing = (
        report.legal_assessments[0]
        if report.legal_assessments
        else report.case_fact_pack.legal_assessments[0]
        if report.case_fact_pack.legal_assessments
        else None
    )
    if not existing:
        return

    case_evidence_id = _primary_report_evidence_id(report)
    evidence_ids = [item for item in (case_evidence_id, legal_evidence_id) if item]
    assessment = existing.model_copy(
        update={
            "provision_reference": "Thanoy legal AI preliminary assessment",
            "preliminary_relevance": advice,
            "status": "inferred",
            "evidence_ids": evidence_ids,
        }
    )
    report.legal_assessments = [assessment]
    report.case_fact_pack.legal_assessments = [assessment]


def _primary_report_evidence_id(report: CyberCaseReport) -> str:
    for evidence in report.case_fact_pack.evidence_registry:
        if evidence.source_type in {"user_input", "uploaded_file", "log"}:
            return evidence.evidence_id
    if report.case_fact_pack.evidence_registry:
        return report.case_fact_pack.evidence_registry[0].evidence_id
    return ""


def _next_report_evidence_id(registry: list[EvidenceReference]) -> str:
    used = {item.evidence_id for item in registry}
    index = 1
    while f"E-{index:03d}" in used:
        index += 1
    return f"E-{index:03d}"


def _needs_report_followup(case_fact_pack) -> bool:
    return case_fact_pack.completeness.status == "Incomplete - follow-up required"


def _start_report_followup(
    request: QueryRequest, req: Request, case_fact_pack
) -> ReportWorkflowResponse:
    rag_agent = req.app.state.rag_agent
    followup_question = _build_report_followup_question(case_fact_pack)
    session_id = ""
    agent_backed = False

    if rag_agent:
        try:
            response: AgentResponse = rag_agent.query(request.query, verbose=False)
            if response.status == "followup" and response.session_id:
                followup_question = response.followup_question or followup_question
                session_id = response.session_id
                agent_backed = True
        except Exception as exc:
            print(f"[REPORT] Agent follow-up fallback: {exc}")

    if not session_id:
        session_id = str(uuid.uuid4())

    req.app.state.report_sessions[session_id] = {
        "request": request.model_dump(mode="json"),
        "agent_backed": agent_backed,
    }
    return ReportWorkflowResponse(
        status="followup",
        followup_question=followup_question,
        session_id=session_id,
        case_fact_pack=case_fact_pack,
        completeness=case_fact_pack.completeness,
        missing_information=case_fact_pack.missing_information,
        retrieval_context_id=request.retrieval_context_id,
    )


def _build_report_followup_question(case_fact_pack) -> str:
    if not case_fact_pack.missing_information:
        return "Could you provide any additional evidence or timeline details before report generation?"
    first_missing = case_fact_pack.missing_information[0]
    return (
        "The preliminary report is incomplete. Please provide the "
        f"{first_missing}, if known. You can answer 'unknown' if unavailable."
    )


def _get_stored_report(report_id: str, req: Request) -> CyberCaseReport:
    report = req.app.state.report_store.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
