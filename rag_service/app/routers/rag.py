from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Request

from RAG.GraphRAG.pipeline.mitre_table import build_mitre_table
from routers.context_store import (
    export_retrieval_context,
    load_retrieval_context,
    store_retrieval_context,
)
from schemas.rag import QueryRequest, QueryResponse, RetrievalContextSnapshot

logger = logging.getLogger(__name__)

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
        agent_response = rag_agent.query(request.query, verbose=False)
        # Keep the old answer-grounded MITRE selection inside rag-service. The
        # generated answer is used only as an internal relevance signal; it is
        # deliberately excluded from the HTTP response and context snapshot.
        mitre_table = build_mitre_table(
            agent_response.graphrag_result,
            agent_response.answer,
        )
        retrieval_context_id = store_retrieval_context(
            req,
            query=request.query,
            context=agent_response.context,
            rag_result=agent_response.graphrag_result,
            mitre_table=mitre_table,
        )
        return QueryResponse(
            status="completed",
            retrieval_context_id=retrieval_context_id or None,
            context=agent_response.context,
            mitre_table=mitre_table,
        )
    except Exception as e:
        logger.exception("POST /query processing failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/retrieval-contexts/{context_id}",
    response_model=RetrievalContextSnapshot,
)
async def get_retrieval_context(context_id: str, req: Request):
    cached = load_retrieval_context(req, context_id)
    if not cached:
        raise HTTPException(status_code=404, detail="Retrieval context not found")

    snapshot = export_retrieval_context(req, context_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Retrieval context not found")
    return RetrievalContextSnapshot.model_validate(snapshot)
