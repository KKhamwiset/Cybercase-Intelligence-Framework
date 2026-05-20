from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    from RAG import GraphRAGChain

    rag_chain = GraphRAGChain()
except ImportError as e:
    import traceback

    print(f"[RAG] Failed to import GraphRAGChain: {e}")
    traceback.print_exc()
    rag_chain = None
except Exception as e:
    import traceback

    print(f"[RAG] Error initializing GraphRAGChain: {e}")
    traceback.print_exc()
    rag_chain = None

router = APIRouter(prefix="/rag", tags=["rag"])


class QueryRequest(BaseModel):
    query: str


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
