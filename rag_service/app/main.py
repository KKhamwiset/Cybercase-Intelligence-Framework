import os
import sys
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add the current directory to sys.path so we can import RAG
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from RAG import AgentResponse, GraphRAGAgent, GraphRAGChain

    rag_chain = GraphRAGChain()
    rag_agent = GraphRAGAgent()
except Exception as e:
    print(f"[RAG Service] Error initializing RAG modules: {e}")
    import traceback

    traceback.print_exc()
    rag_chain = None
    rag_agent = None

app = FastAPI(title="Cybercase RAG Service")


class QueryRequest(BaseModel):
    query: str
    use_agent: bool = False


class QueryResponse(BaseModel):
    status: str  # "completed" | "followup"
    answer: str = ""
    followup_question: str = ""
    session_id: str = ""


class ResumeRequest(BaseModel):
    session_id: str
    answer: str


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "rag_chain": rag_chain is not None,
        "rag_agent": rag_agent is not None,
    }


@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    if request.use_agent:
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
async def resume_agent(request: ResumeRequest):
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
