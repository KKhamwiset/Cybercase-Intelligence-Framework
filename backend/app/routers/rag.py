from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.report_request_helpers import build_document_query
from app.schemas.rag import QueryRequest, QueryResponse, RagQueryRequest
from app.services.rag_client import RagServiceClient
from app.services.typhoon_ocr_reader import extract_markdown_from_upload

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    payload = await RagServiceClient().post_json(
        "/query",
        request.model_dump(mode="json"),
    )
    return QueryResponse(**payload)


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
        request = RagQueryRequest(query=document_query, use_agent=False)
        payload = request.model_dump(mode="json")
        payload["legal"] = legal
        payload = await RagServiceClient().post_json(
            "/query",
            payload,
        )
        return QueryResponse(**payload)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[RAG] Error processing OCR query: {e}")
        raise HTTPException(status_code=500, detail=str(e))
