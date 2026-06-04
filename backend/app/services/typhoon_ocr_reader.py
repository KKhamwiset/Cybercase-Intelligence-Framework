import os
import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile


SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


async def extract_markdown_from_upload(file: UploadFile, page_num: int = 1) -> str:
    """Run Typhoon OCR on one uploaded PDF/image and return Markdown text."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload a PDF, PNG, JPG, or JPEG file.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds 25 MB.")

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        typhoon_api_key = (
            os.getenv("TYPHOON_OCR_API_KEY")
            or os.getenv("TYPHOON_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        if not typhoon_api_key:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Typhoon OCR API key is missing. Set TYPHOON_OCR_API_KEY, "
                    "TYPHOON_API_KEY, or OPENAI_API_KEY."
                ),
            )
        if not os.getenv("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = typhoon_api_key

        try:
            from typhoon_ocr import ocr_document
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail="Typhoon OCR is not installed in the backend environment.",
            ) from exc

        markdown = ocr_document(pdf_or_image_path=temp_path, page_num=page_num)
        if not markdown or not markdown.strip():
            raise HTTPException(status_code=422, detail="Typhoon OCR returned empty text.")

        return markdown.strip()
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
