# CyberCase Intelligence Framework

CyberCase is a single-user chat application for MITRE ATT&CK-assisted cybersecurity incident analysis. A Next.js frontend stores chat activity through a FastAPI backend, and the backend sends each analysis request to the standalone GraphRAG service.

The current product boundary is intentionally narrow:

- PostgreSQL persists chat threads, messages, and background runs.
- The backend exposes health and chat APIs only.
- The RAG service owns retrieval and answer generation.
- Interactive clarification is owned by the backend. Each clarification round sends a new RAG `/query` containing the accumulated incident context.
- The frontend can assemble an extraction view and a seven-section report for the selected chat. That report is a demo-only, client-side, non-persistent, unverified artifact; it is not a backend case report.

The application is not ready for multi-user deployment because the chat routes do not yet enforce authentication or per-user ownership.

## Services

| Service | Path | Port | Responsibility |
| --- | --- | --- | --- |
| Frontend | `frontend/` | 3000 | Chat UI plus client-side demo extraction/report views |
| Backend | `backend/` | 8000 | Chat persistence, background runs, clarification policy, and RAG orchestration |
| RAG service | `rag_service/` | 8001 | GraphRAG retrieval and answer generation through `/query` |
| PostgreSQL | Compose service `db` | 5433 on the host | Persistent chat data |

Neo4j and Qdrant are external services used by `rag_service`.

## Quick Start

### Docker Compose

Doppler supplies the API keys and external database settings consumed by the services:

```powershell
doppler run -- docker compose up --build
```

This starts PostgreSQL, the backend, the RAG service, and the frontend. The named PostgreSQL volume is persistent; do not use `docker compose down -v` unless deleting local database data is intentional.

Apply the database migrations after the database is available. The migration graph has a single current head:

```powershell
cd backend
doppler run -- python -m alembic upgrade head
```

### Local Development

Create and activate a Python environment, then install the backend and RAG dependencies:

```powershell
python -m venv env_mitre
.\env_mitre\Scripts\Activate.ps1
python install_deps.py
```

Run each service in its own terminal:

```powershell
cd rag_service
doppler run -- uvicorn app.main:app --port 8001 --reload
```

```powershell
cd backend
doppler run -- python -m alembic upgrade head
doppler run -- uvicorn app.main:app --port 8000 --reload
```

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000/chat`. Backend OpenAPI documentation is available at `http://localhost:8000/docs`.

## Backend API

All application endpoints use the `/api/v1` prefix.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Check backend and database health |
| `GET` | `/api/v1/chats` | List chat threads |
| `POST` | `/api/v1/chats` | Create a chat thread |
| `GET` | `/api/v1/chats/{thread_id}` | Read a thread and its ordered messages |
| `PATCH` | `/api/v1/chats/{thread_id}` | Rename a thread |
| `DELETE` | `/api/v1/chats/{thread_id}` | Permanently delete a thread and its dependent rows |
| `POST` | `/api/v1/chats/{thread_id}/messages` | Persist a user message and enqueue a background run |
| `GET` | `/api/v1/chats/{thread_id}/runs/{run_id}` | Read a known background run's status or error |

There are no backend case, report, user, upload/OCR, or standalone RAG-proxy routes in the chat-only application.

## Chat and Clarification Flow

1. The frontend creates or selects a persisted chat thread.
2. Posting a message returns `202 Accepted` with the stored message and queued run.
3. The backend worker calls `rag_service` at `POST /query`.
4. The backend evaluates whether the accumulated incident context needs a focused clarification.
5. If clarification is needed, the assistant question is persisted and the thread enters `awaiting_followup`.
6. A clarification answer is stored as a normal user message. The backend reconstructs the active clarification chain and starts another `/query` with the original incident text plus accumulated questions and answers.
7. The frontend polls the authoritative thread state until the run is complete or failed.

The frontend never calls `rag_service` directly, and the chat flow does not call a RAG `/resume` endpoint.

## Demo Report Boundary

The Report tab reads the currently selected chat and builds its output in the browser. It does not create a report record, invoke a backend report workflow, or verify the underlying evidence. Refreshing or switching away does not create a separately persisted report artifact. Treat the output as a demonstration draft requiring human review, not an investigation finding or legal conclusion.

## Validation

```powershell
cd backend
..\env_mitre\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
python -m alembic heads
```

```powershell
cd frontend
npm run lint
npm run test
npm run build
```

```powershell
docker compose config --quiet
```

See `docs/chat-frontend-backend-integration.md` for the detailed frontend/backend chat contract.
