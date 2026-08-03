"""Bounded smoke test for a running chat-only backend."""

from __future__ import annotations

import os
import time
from uuid import uuid4

import httpx


BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")
POLL_INTERVAL_SECONDS = 0.5
POLL_TIMEOUT_SECONDS = 60.0
RUN_TERMINAL_STATUSES = {"completed", "failed"}
THREAD_TERMINAL_STATUSES = {"idle", "awaiting_followup", "failed"}


def _require_success(response: httpx.Response) -> dict[str, object]:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Backend returned a non-object JSON response")
    return payload


def main() -> None:
    thread_id: str | None = None
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        try:
            thread = _require_success(
                client.post("/api/v1/chats", json={"title": "Manual smoke chat"})
            )
            thread_id = str(thread["id"])
            accepted = _require_success(
                client.post(
                    f"/api/v1/chats/{thread_id}/messages",
                    json={
                        "content": "Summarize suspicious PowerShell activity.",
                        "idempotency_key": f"manual-smoke-{uuid4()}",
                    },
                )
            )
            run = accepted["run"]
            if not isinstance(run, dict):
                raise RuntimeError("Chat acceptance response omitted its run")
            run_id = str(run["id"])

            deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                run = _require_success(
                    client.get(f"/api/v1/chats/{thread_id}/runs/{run_id}")
                )
                thread = _require_success(client.get(f"/api/v1/chats/{thread_id}"))
                if (
                    run.get("status") in RUN_TERMINAL_STATUSES
                    and thread.get("status") in THREAD_TERMINAL_STATUSES
                ):
                    print(
                        "Chat smoke reached terminal state: "
                        f"run={run['status']} thread={thread['status']}"
                    )
                    return
                time.sleep(POLL_INTERVAL_SECONDS)

            raise TimeoutError(
                f"Chat smoke did not finish within {POLL_TIMEOUT_SECONDS:.0f} seconds"
            )
        finally:
            if thread_id is not None:
                response = client.delete(f"/api/v1/chats/{thread_id}")
                response.raise_for_status()


if __name__ == "__main__":
    main()
