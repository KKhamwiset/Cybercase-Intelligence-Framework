from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import Request

RETRIEVAL_CONTEXT_TTL_SECONDS = 60 * 60


def get_retrieval_contexts(req: Request) -> dict[str, dict[str, Any]]:
    contexts = getattr(req.app.state, "retrieval_contexts", None)
    if contexts is None:
        contexts = {}
        req.app.state.retrieval_contexts = contexts
    return contexts


def prune_retrieval_contexts(req: Request) -> None:
    contexts = get_retrieval_contexts(req)
    now = time.time()
    expired_ids = [
        context_id
        for context_id, cached in contexts.items()
        if cached.get("expires_at", 0) <= now
    ]
    for context_id in expired_ids:
        contexts.pop(context_id, None)


def store_retrieval_context(
    req: Request,
    *,
    query: str,
    context: str,
    rag_result: Any,
) -> str:
    if not context or rag_result is None:
        return ""

    prune_retrieval_contexts(req)
    context_id = str(uuid.uuid4())
    now = time.time()
    get_retrieval_contexts(req)[context_id] = {
        "query": query,
        "context": context,
        "rag_result": rag_result,
        "created_at": now,
        "expires_at": now + RETRIEVAL_CONTEXT_TTL_SECONDS,
    }
    return context_id


def load_retrieval_context(req: Request, context_id: str) -> dict[str, Any] | None:
    if not context_id:
        return None

    prune_retrieval_contexts(req)
    cached = get_retrieval_contexts(req).get(context_id)
    if cached:
        cached["expires_at"] = time.time() + RETRIEVAL_CONTEXT_TTL_SECONDS
    return cached
