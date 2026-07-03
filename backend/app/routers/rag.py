import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.routers.report import build_document_query
from app.schemas.rag import QueryRequest, QueryResponse, ResumeRequest
from app.services.typhoon_ocr_reader import extract_markdown_from_upload

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(
                f"{settings.rag_service_url}/query",
                json=request.model_dump(mode="json"),
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
    page_num: str | None = Form(None),
    legal: bool = Form(False),
):
    try:
        extracted_markdown = await extract_markdown_from_upload(file, page_num=page_num)
        document_query = build_document_query(extracted_markdown, query)

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{settings.rag_service_url}/query",
                json={"query": document_query, "use_agent": False, "legal": legal},
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
                json=request.model_dump(mode="json"),
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
