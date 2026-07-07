import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.legacy import (
    LegacyReportWorkflowResponse,
    legacy_report_response_from_payload,
)
from app.schemas.report import (
    EvidenceReference,
    ReportRequest,
    ReportResumeRequest,
    ReviewStatusUpdate,
)
from app.services.rag_client import RagServiceClient
from app.services.typhoon_ocr_reader import extract_markdown_from_upload

router = APIRouter(prefix="/rag", tags=["reports"])


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


def hash_bytes_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


async def hash_upload_and_rewind(file: UploadFile) -> str:
    content = await file.read()
    await file.seek(0)
    return hash_bytes_sha256(content)


def build_upload_evidence_registry(
    *,
    query: str,
    file: UploadFile,
    extracted_markdown: str,
    file_hash_sha256: str,
    page_num: str | None,
) -> list[EvidenceReference]:
    registry: list[EvidenceReference] = []
    next_id = 1
    if query.strip():
        registry.append(
            EvidenceReference(
                evidence_id=f"E-{next_id:03d}",
                source_type="user_input",
                source_name="Submitted case text",
                excerpt=query.strip()[:1200],
            )
        )
        next_id += 1

    page_number: int | None = None
    if page_num and page_num.isdigit():
        page_number = int(page_num)

    registry.append(
        EvidenceReference(
            evidence_id=f"E-{next_id:03d}",
            source_type="uploaded_file",
            source_name=file.filename or "uploaded file",
            excerpt=extracted_markdown[:1200],
            page_number=page_number,
            file_hash_sha256=file_hash_sha256,
            content_type=file.content_type,
            uploaded_at=datetime.now(timezone.utc).isoformat(),
            extraction_method="typhoon_ocr",
        )
    )
    return registry


@router.post("/generate-report", response_model=LegacyReportWorkflowResponse)
async def generate_report(request: ReportRequest):
    payload = await RagServiceClient().post_json(
        "/generate-report",
        request.model_dump(mode="json"),
    )
    return legacy_report_response_from_payload(payload)


@router.post("/generate-report-file", response_model=LegacyReportWorkflowResponse)
async def generate_report_file(
    file: UploadFile = File(...),
    query: str = Form(""),
    report_type: str = Form("overview"),
    legal: bool = Form(False),
    force_generate: bool = Form(False),
    page_num: str | None = Form(None),
):
    try:
        file_hash_sha256 = await hash_upload_and_rewind(file)
        extracted_markdown = await extract_markdown_from_upload(file, page_num=page_num)
        document_query = build_document_query(extracted_markdown, query)
        evidence_registry = build_upload_evidence_registry(
            query=query,
            file=file,
            extracted_markdown=extracted_markdown,
            file_hash_sha256=file_hash_sha256,
            page_num=page_num,
        )
        payload = ReportRequest(
            query=document_query,
            report_type=report_type,  # type: ignore[arg-type]
            legal=legal,
            force_generate=force_generate,
            evidence_registry=evidence_registry,
        )
        response_payload = await RagServiceClient().post_json(
            "/generate-report",
            payload.model_dump(mode="json"),
        )
        return legacy_report_response_from_payload(response_payload)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[RAG] Error generating OCR report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume-report", response_model=LegacyReportWorkflowResponse)
async def resume_report(request: ReportResumeRequest):
    payload = await RagServiceClient().post_json(
        "/resume-report",
        request.model_dump(mode="json"),
    )
    return legacy_report_response_from_payload(payload)


@router.get("/reports/{report_id}", response_model=LegacyReportWorkflowResponse)
async def get_report(report_id: str):
    payload = await RagServiceClient().get_json(f"/reports/{report_id}")
    return legacy_report_response_from_payload(payload)


@router.patch(
    "/reports/{report_id}/review-status",
    response_model=LegacyReportWorkflowResponse,
)
async def update_report_review_status(report_id: str, request: ReviewStatusUpdate):
    payload = await RagServiceClient().patch_json(
        f"/reports/{report_id}/review-status",
        request.model_dump(mode="json"),
    )
    return legacy_report_response_from_payload(payload)
