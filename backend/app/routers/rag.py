import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import settings
from app.services.typhoon_ocr_reader import extract_markdown_from_upload

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
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(
                f"{settings.rag_service_url}/query",
                json=request.model_dump(),
            )
            response.raise_for_status()
            return QueryResponse(**response.json())
        except httpx.HTTPStatusError as e:
            print(f"[RAG] Service error: {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code, detail=e.response.text
            )
        except Exception as e:
            print(f"[RAG] Error calling RAG service: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/query-file", response_model=QueryResponse)
async def query_rag_file(
    file: UploadFile = File(...),
    query: str = Form(""),
    page_num: int = Form(1),
):
    if page_num < 1:
        raise HTTPException(status_code=400, detail="page_num must be 1 or greater")

    try:
        extracted_markdown = await extract_markdown_from_upload(file, page_num=page_num)
        document_query = build_document_query(extracted_markdown, query)

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{settings.rag_service_url}/query",
                json={"query": document_query, "use_agent": False},
            )
            response.raise_for_status()
            return QueryResponse(**response.json())
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        print(f"[RAG] Service error: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        print(f"[RAG] Error processing OCR query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume", response_model=QueryResponse)
async def resume_agent(request: ResumeRequest):
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(
                f"{settings.rag_service_url}/resume",
                json=request.model_dump(),
            )
            response.raise_for_status()
            return QueryResponse(**response.json())
        except httpx.HTTPStatusError as e:
            print(f"[RAG] Service error: {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code, detail=e.response.text
            )
        except Exception as e:
            print(f"[RAG] Error calling RAG service: {e}")
            raise HTTPException(status_code=500, detail=str(e))
