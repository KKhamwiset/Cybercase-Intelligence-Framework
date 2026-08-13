# Current Architecture

## System boundary

```text
Next.js frontend (:3000)
        |
        v
Backend FastAPI (:8000) ---- PostgreSQL
        |
        v
RAG FastAPI service (:8001) ---- Qdrant + Neo4j
```

The backend owns persistent chat threads, message ordering, idempotency,
follow-up policy, extraction orchestration, Case State versions, durable RAG
context, and Main Case Analysis orchestration. The RAG service owns external
MITRE retrieval and its LangGraph agent. The frontend does not call the RAG
service directly.

The backend currently exposes health plus chat-scoped routes. In addition to
thread/message/run routes, `backend/app/routers/chat.py` currently exposes
chat-scoped report generation, listing, retrieval, and PDF routes under
`/api/v1/chats/{thread_id}/reports`. There is no standalone top-level
`/api/v1/reports` or case route. Do not add a new backend RAG proxy or a new
case/report surface without an explicit product decision.

The RAG service separately exposes `/health`, `/query`, and its retrieval
context inspection route. Older root guidance and some README text still say
that reports are client-only; that is documentation drift, not the current
route implementation. Verify the router and tests before changing report
behavior.

## Initial message lifecycle

1. `POST /api/v1/chats/{thread_id}/messages` creates the user message and a
   queued `ChatRun` in one backend transaction.
2. The worker evaluates the clarification policy. A clarification response can
   terminate the run as `awaiting_followup` without retrieval.
3. For a normal terminal path, the worker runs validated source-bounded Case
   State extraction from user-authored case messages only.
4. The worker calls RAG `/query`. The RAG agent runs its full pipeline, but its
   generated answer is not accepted at the backend wire boundary.
5. The worker passes the validated Case State plus retrieval context and MITRE
   rows to Main Case Analysis with `question=None`.
6. Completion persists the assistant analysis, a new `CaseStateVersion`, and a
   `RagContext` atomically, then advances the thread pointer and run status.

Relevant implementation paths:

- `backend/app/services/chat/chat_message.py`
- `backend/app/services/chat/chat_worker.py`
- `backend/app/services/chat/case_state_mutation.py`
- `backend/app/services/chat/extraction_stage.py`
- `backend/app/services/chat/outcome_mapper.py`
- `backend/app/services/case_analysis/service.py`

## Post-answer lifecycle

An answered thread requires an explicit message action:

- `ask` reuses the current Case State version and its one-to-one `RagContext`,
  invokes Main Case Analysis with the new question, and must not invoke RAG,
  extraction, or Case State mutation.
- `add_case_info` is an explicit mutation route. It extracts a narrow delta
  from the current Case State plus the new user message, applies that delta
  deterministically, invokes fresh RAG and `case_overview` analysis, then
  atomically persists the child Case State version, fresh `RagContext`, and
  assistant result. A `no_change` delta leaves the current version untouched.

The frontend action selector lives in `ChatPanel`; state and request forwarding
live in `ChatWorkspace`. The action is included in the idempotency matching so
the same text submitted as `ask` and `add_case_info` cannot reuse one key.

## Persistence invariant

`CaseStateVersion` is immutable history. `ChatThread.current_case_state_version_id`
points to the version used by the current answer. `RagContext` is bound by a
composite `(thread_id, case_state_version_id)` foreign key and has a unique
`case_state_version_id`, so each state version has at most one durable retrieval
snapshot. The backend migration chain is currently headed by
`backend/alembic/baseline_versions/0005_rag_contexts.py`.
