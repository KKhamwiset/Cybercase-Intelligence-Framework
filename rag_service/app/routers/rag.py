from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from RAG import AgentResponse
from routers.context_store import store_retrieval_context
from schemas.rag import QueryRequest, QueryResponse, ResumeRequest

router = APIRouter(tags=["rag"])


@router.get("/health")
async def health(request: Request):
    return {
        "status": "ok",
        "rag_chain": request.app.state.rag_chain is not None,
        "rag_agent": request.app.state.rag_agent is not None,
    }


@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest, req: Request):
    rag_agent = req.app.state.rag_agent
    rag_chain = req.app.state.rag_chain

    if request.use_agent:
        print("Agent requested")
        if not rag_agent:
            raise HTTPException(status_code=503, detail="RAG Agent not available")
        try:
            response: AgentResponse = rag_agent.query(request.query)
            retrieval_context_id = store_retrieval_context(
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


@router.post("/resume", response_model=QueryResponse)
async def resume_agent(request: ResumeRequest, req: Request):
    rag_agent = req.app.state.rag_agent
    if not rag_agent:
        raise HTTPException(status_code=503, detail="RAG Agent not available")
    try:
        response: AgentResponse = rag_agent.resume(request.session_id, request.answer)
        retrieval_context_id = store_retrieval_context(
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
