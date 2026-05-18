import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Add project root to path to allow importing RAG modules
# In Docker, the app is at /app, RAG is at /app/RAG
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

try:
    from app.services.rag.pipeline.chain import GraphRAGChain

    rag_chain = GraphRAGChain()
except ImportError as e:
    print(f"[RAG] Failed to import GraphRAGChain: {e}")
    rag_chain = None
except Exception as e:
    print(f"[RAG] Error initializing GraphRAGChain: {e}")
    rag_chain = None

router = APIRouter(prefix="/rag", tags=["rag"])


class QueryRequest(BaseModel):
    query: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatContinueRequest(BaseModel):
    query: str
    history: list[ChatMessage]


class QueryResponse(BaseModel):
    answer: str


@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    if not rag_chain:
        raise HTTPException(
            status_code=503, detail="RAG engine not initialized or available"
        )

    try:
        # Note: rag_chain.query is a synchronous call.
        # In a real high-traffic app, we should use run_in_threadpool or make the chain async.
        # But for now, we'll keep it simple.
        answer = rag_chain.query(request.query)
        return QueryResponse(answer=answer)
    except Exception as e:
        print(f"[RAG] Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chatcontinue", response_model=QueryResponse)
async def chat_continue(request: ChatContinueRequest):
    """
    Endpoint for continuous chat that accepts current query and history.
    """
    if not rag_chain:
        raise HTTPException(
            status_code=503, detail="RAG engine not initialized or available"
        )

    try:
        # For now, we pass the query to the RAG engine.
        # In the future, you can incorporate 'request.history' into the prompt
        # to provide context-aware answers.
        answer = rag_chain.query(request.query)
        return QueryResponse(answer=answer)
    except Exception as e:
        print(f"[RAG] Error processing chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))
