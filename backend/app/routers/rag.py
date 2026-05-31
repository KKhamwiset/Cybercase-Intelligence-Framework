from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.typhoon_ocr_reader import extract_markdown_from_upload

try:
    from RAG import GraphRAGChain, GraphRAGAgent, AgentResponse

    rag_chain = GraphRAGChain()
    rag_agent = GraphRAGAgent()
except ImportError as e:
    import traceback

    print(f"[RAG] Failed to import RAG modules: {e}")
    traceback.print_exc()
    rag_chain = None
    rag_agent = None
except Exception as e:
    import traceback

    print(f"[RAG] Error initializing RAG modules: {e}")
    traceback.print_exc()
    rag_chain = None
    rag_agent = None

router = APIRouter(prefix="/rag", tags=["rag"])


class QueryRequest(BaseModel):
    query: str
    use_agent: bool = False  # Set to true to use LangGraph agent


class QueryResponse(BaseModel):
    status: str  # "completed" | "followup"
    answer: str = ""
    followup_question: str = ""
    session_id: str = ""


class ResumeRequest(BaseModel):
    session_id: str
    answer: str


def build_document_query(extracted_markdown: str, query: str | None) -> str:
    user_query = (query or "").strip()
    if not user_query:
        user_query = "Analyze this document and identify the most relevant cyber threat, legal, or MITRE ATT&CK context."

    return (
        f"{user_query}\n\n"
        "Document extracted by Typhoon OCR:\n"
        "```markdown\n"
        f"{extracted_markdown}\n"
        "```"
    )


@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    if request.use_agent:
        if not rag_agent:
            raise HTTPException(
                status_code=503, detail="RAG Agent not initialized or available"
            )
        try:
            response: AgentResponse = rag_agent.query(request.query)
            return QueryResponse(
                status=response.status,
                answer=response.answer,
                followup_question=response.followup_question,
                session_id=response.session_id,
            )
        except Exception as e:
            print(f"[RAG] Error processing agent query: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Linear chain (backward compatible)
        if not rag_chain:
            raise HTTPException(
                status_code=503, detail="RAG Chain not initialized or available"
            )
        try:
            answer = rag_chain.query(request.query)
            return QueryResponse(status="completed", answer=answer)
        except Exception as e:
            print(f"[RAG] Error processing chain query: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/query-file", response_model=QueryResponse)
async def query_rag_file(
    file: UploadFile = File(...),
    query: str = Form(""),
    page_num: int = Form(1),
):
    if not rag_chain:
        raise HTTPException(
            status_code=503, detail="RAG Chain not initialized or available"
        )

    if page_num < 1:
        raise HTTPException(status_code=400, detail="page_num must be 1 or greater")

    try:
        extracted_markdown = await extract_markdown_from_upload(file, page_num=page_num)
        answer = rag_chain.query(build_document_query(extracted_markdown, query))
        return QueryResponse(status="completed", answer=answer)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[RAG] Error processing OCR query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume", response_model=QueryResponse)
async def resume_agent(request: ResumeRequest):
    if not rag_agent:
        raise HTTPException(
            status_code=503, detail="RAG Agent not initialized or available"
        )
    
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
        print(f"[RAG] Error resuming agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))
