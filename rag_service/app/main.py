import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

# Add the current directory to sys.path so we can import RAG
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from RAG import (
    AgentResponse,
    CyberCaseReport,
    GraphRAGAgent,
    GraphRAGChain,
    HybridRetriever,
    ReportGenerator,
    build_context,
    build_retrieval_queries,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    print("[RAG Service] Initializing RAG modules...")
    try:
        from FlagEmbedding import BGEM3FlagModel
        from RAG.GraphRAG.config import EMBED_MODEL, RERANKER_MODEL, USE_FP16
        from RAG.GraphRAG.retrieval.reranker import Reranker

        # 1. Load heavy models once
        print(f"[RAG Service] Loading shared embedding model: {EMBED_MODEL}")
        embed_model = BGEM3FlagModel(EMBED_MODEL, use_fp16=USE_FP16)

        print(f"[RAG Service] Loading shared reranker model: {RERANKER_MODEL}")
        reranker_model = Reranker(RERANKER_MODEL)

        # 2. Initialize components with shared models
        app.state.rag_chain = GraphRAGChain(
            embed_model=embed_model, reranker=reranker_model
        )
        app.state.rag_agent = GraphRAGAgent(
            embed_model=embed_model, reranker=reranker_model
        )
        app.state.retriever = HybridRetriever(
            embed_model=embed_model, reranker=reranker_model
        )

        app.state.report_gen = ReportGenerator()
        print("[RAG Service] RAG modules initialized successfully.")

    except Exception as e:
        print(f"[RAG Service] Error initializing RAG modules: {e}")
        import traceback

        traceback.print_exc()
        app.state.rag_chain = None
        app.state.rag_agent = None
        app.state.retriever = None
        app.state.report_gen = None

    yield

    # Shutdown
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


class QueryResponse(BaseModel):
    status: str  # "completed" | "followup"
    answer: str = ""
    followup_question: str = ""
    session_id: str = ""


class ResumeRequest(BaseModel):
    session_id: str
    answer: str


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
            return QueryResponse(
                status=response.status,
                answer=response.answer,
                followup_question=response.followup_question,
                session_id=response.session_id,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
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
        return QueryResponse(
            status=response.status,
            answer=response.answer,
            followup_question=response.followup_question,
            session_id=response.session_id,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-report", response_model=CyberCaseReport)
async def generate_report(request: QueryRequest, req: Request):
    retriever = req.app.state.retriever
    report_gen = req.app.state.report_gen

    if not retriever or not report_gen:
        raise HTTPException(
            status_code=503, detail="Report Generator or Retriever not available"
        )

    try:
        # 1. Translate (Thai → English) and retrieve via dual-query
        print(f"[REPORT] Generating report for: {request.query[:50]}...")
        rag_chain = req.app.state.rag_chain
        english_query = (
            rag_chain.translator.translate_query(request.query)
            if rag_chain
            else request.query
        )
        queries = build_retrieval_queries(request.query, english_query)
        rag_result = retriever.retrieve_multi(queries)
        context = build_context(rag_result)

        # 2. Generate structured report
        report = report_gen.generate(request.query, context)
        return report
    except Exception as e:
        print(f"[REPORT] Error: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
