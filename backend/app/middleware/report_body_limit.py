from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

ANALYSIS_PATH_PREFIX = "/api/v1/rag/cases/"
ANALYSIS_PATH_SUFFIX = "/experimental-analysis"
REPORT_REQUEST_BODY_LIMIT_BYTES = 512 * 1024


class ReportBodyLimitMiddleware:
    """Reject oversized experimental-analysis bodies before model validation."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_bytes: int = REPORT_REQUEST_BODY_LIMIT_BYTES,
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self._applies(scope):
            await self.app(scope, receive, send)
            return

        content_length = self._content_length(scope)
        if content_length is not None and content_length > self.max_bytes:
            await self._reject(scope, receive, send)
            return

        buffered_body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            body = message.get("body", b"")
            if len(buffered_body) + len(body) > self.max_bytes:
                await self._reject(scope, receive, send)
                return
            buffered_body.extend(body)
            if not message.get("more_body", False):
                break

        replay_pending = True

        async def replay_receive() -> Message:
            nonlocal replay_pending
            if replay_pending:
                replay_pending = False
                return {
                    "type": "http.request",
                    "body": bytes(buffered_body),
                    "more_body": False,
                }
            return await receive()

        await self.app(scope, replay_receive, send)

    @staticmethod
    def _applies(scope: Scope) -> bool:
        return (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and scope.get("path", "").startswith(ANALYSIS_PATH_PREFIX)
            and scope.get("path", "").endswith(ANALYSIS_PATH_SUFFIX)
        )

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        for name, value in scope.get("headers", []):
            if name.lower() != b"content-length":
                continue
            try:
                parsed = int(value)
            except ValueError:
                return None
            return parsed if parsed >= 0 else None
        return None

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            status_code=413,
            content={
                "detail": (
                    "Experimental analysis request body exceeds the "
                    f"{self.max_bytes}-byte limit"
                )
            },
        )
        await response(scope, receive, send)
