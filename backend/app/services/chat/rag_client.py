"""Typed HTTP boundary for chat requests to the RAG service."""

from __future__ import annotations

from typing import Literal

import httpx
from pydantic import ValidationError

from app.config import settings
from app.schemas.rag import QueryRequest, QueryResponse, ResumeRequest


RAG_HTTP_TIMEOUT_SECONDS = 300.0


class RagCallFailure(Exception):
    """A safe, stable failure that may be persisted on a chat run."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def request_rag(
    operation: Literal["query", "resume"],
    content: str,
    input_rag_session_id: str | None,
    *,
    client: httpx.AsyncClient | None = None,
) -> QueryResponse:
    """Call the matching RAG endpoint and validate its public response contract."""

    if operation == "query":
        endpoint = "/query"
        payload = QueryRequest(query=content, use_agent=True).model_dump()
    elif input_rag_session_id:
        endpoint = "/resume"
        payload = ResumeRequest(
            session_id=input_rag_session_id,
            answer=content,
        ).model_dump()
    else:
        raise ValueError("A resume run requires an input RAG session ID")

    url = f"{settings.rag_service_url.rstrip('/')}{endpoint}"
    if client is not None:
        return await _post_and_validate(client, url, payload, operation)

    async with httpx.AsyncClient(timeout=RAG_HTTP_TIMEOUT_SECONDS) as owned_client:
        return await _post_and_validate(owned_client, url, payload, operation)


async def _post_and_validate(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, object],
    operation: Literal["query", "resume"],
) -> QueryResponse:
    try:
        response = await client.post(url, json=payload)
    except httpx.TimeoutException as exc:
        raise RagCallFailure(
            "rag_timeout",
            "RAG service request timed out",
        ) from exc
    except httpx.RequestError as exc:
        raise RagCallFailure(
            "rag_service_error",
            "RAG service request failed",
        ) from exc

    if operation == "resume" and response.status_code == 404:
        raise RagCallFailure(
            "rag_session_expired",
            "Failed to recover follow-up session",
        )
    if not 200 <= response.status_code < 300:
        raise RagCallFailure(
            "rag_service_error",
            "RAG service request failed",
        )

    try:
        response_payload = response.json()
        return QueryResponse.model_validate(response_payload)
    except (ValueError, ValidationError, TypeError) as exc:
        raise RagCallFailure(
            "rag_invalid_response",
            "RAG service returned an invalid response",
        ) from exc
