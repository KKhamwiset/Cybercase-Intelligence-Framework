import hashlib
from datetime import datetime, timezone

from fastapi import UploadFile

from app.schemas.report import EvidenceReference


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
