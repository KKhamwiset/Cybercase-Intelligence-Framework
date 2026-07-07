from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException

from app.config import settings


class RagServiceClient:
    def __init__(self, base_url: str | None = None, timeout: float = 300.0) -> None:
        self.base_url = (base_url or settings.rag_service_url).rstrip("/")
        self.timeout = timeout

    async def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json("POST", path, json=payload)

    async def patch_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json("PATCH", path, json=payload)

    async def get_json(self, path: str) -> dict[str, Any]:
        return await self._request_json("GET", path)

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(method, url, json=json)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise HTTPException(
                        status_code=502,
                        detail="RAG service returned a non-object response",
                    )
                return payload
            except httpx.HTTPStatusError as exc:
                print(f"[RAG] Service error: {exc.response.text}")
                raise HTTPException(
                    status_code=exc.response.status_code,
                    detail=exc.response.text,
                )
            except HTTPException:
                raise
            except Exception as exc:
                print(f"[RAG] Error calling RAG service: {exc}")
                raise HTTPException(status_code=500, detail=str(exc))


__all__ = ["RagServiceClient"]
