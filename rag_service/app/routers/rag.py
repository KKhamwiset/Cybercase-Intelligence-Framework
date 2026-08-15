from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from RAG import AgentResponse, build_mitre_table
from routers.context_store import (
    export_retrieval_context,
    load_retrieval_context,
    store_retrieval_context,
)
from schemas.rag import QueryRequest, QueryResponse, RetrievalContextSnapshot

router = APIRouter(tags=["rag"])


@router.get("/health")
async def health(request: Request):
    return {
        "status": "ok",
        "rag_agent": request.app.state.rag_agent is not None,
    }


@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest, req: Request):
    rag_agent = req.app.state.rag_agent
    if not rag_agent:
        raise HTTPException(status_code=503, detail="RAG Agent not available")

    try:
        response: AgentResponse = rag_agent.query(request.query)
        mitre_table = build_mitre_table(response.graphrag_result, response.answer)
        retrieval_context_id = store_retrieval_context(
            req,
            query=request.query,
            context=response.context,
            rag_result=response.graphrag_result,
            answer=response.answer,
            mitre_table=mitre_table,
        )
        return QueryResponse(
            status=response.status,
            answer=response.answer,
            retrieval_context_id=retrieval_context_id,
            mitre_table=mitre_table,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/retrieval-contexts/{context_id}",
    response_model=RetrievalContextSnapshot,
)
async def get_retrieval_context(context_id: str, req: Request):
    cached = load_retrieval_context(req, context_id)
    if not cached:
        raise HTTPException(status_code=404, detail="Retrieval context not found")

    if not cached.get("mitre_table") and cached.get("rag_result") and cached.get("answer"):
        cached["mitre_table"] = build_mitre_table(
            cached["rag_result"], cached["answer"]
        )

    snapshot = export_retrieval_context(req, context_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Retrieval context not found")
    return RetrievalContextSnapshot.model_validate(snapshot)
