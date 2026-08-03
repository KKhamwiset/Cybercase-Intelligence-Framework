# CyberCase Chat Backend

This FastAPI service is the persistence and orchestration boundary for the CyberCase chat application. It stores chat threads, messages, and background runs in PostgreSQL, applies the backend-owned clarification policy, and calls the standalone RAG service over HTTP.

It does not expose case, report, user, upload/OCR, or standalone RAG-proxy APIs. The report shown by the frontend is generated client-side for demonstration and is not stored or verified by this service.

## Stack

- FastAPI and Pydantic
- SQLAlchemy async ORM with `asyncpg`
- PostgreSQL
- Alembic migrations
- HTTPX for RAG and clarification-policy calls

## Setup

From the repository root, activate the project environment and install dependencies:

```powershell
.\env_mitre\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

Configure the service through Doppler or a local `.env` file. The relevant settings are:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=cybercase_framework
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
CORS_ORIGINS=http://localhost:3000
RAG_SERVICE_URL=http://localhost:8001
ANTHROPIC_API_KEY=your_key_here
```

The backend runtime and online migrations build their async connection from `POSTGRES_*`. `ANTHROPIC_API_KEY` is used by the backend clarification policy. The RAG service has its own external Neo4j, Qdrant, and model settings.

## Migrations

The retained migration history has one current head. Apply all migrations with:

```powershell
cd backend
python -m alembic upgrade head
```

The legacy case/report cleanup migration is intentionally irreversible because recreating empty tables would not restore deleted records. Restore a verified pre-migration PostgreSQL backup if those records are needed.

## Run

```powershell
cd backend
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; OpenAPI documentation is at `http://localhost:8000/docs`.

## Routes

All application routes use the `/api/v1` prefix.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Check backend and database health |
| `GET` | `/chats` | List threads |
| `POST` | `/chats` | Create a thread |
| `GET` | `/chats/{thread_id}` | Read a thread and ordered messages |
| `PATCH` | `/chats/{thread_id}` | Rename a thread |
| `DELETE` | `/chats/{thread_id}` | Hard-delete a thread and dependent messages/runs |
| `POST` | `/chats/{thread_id}/messages` | Store a message and enqueue a run; returns `202` |
| `GET` | `/chats/{thread_id}/runs/{run_id}` | Read the status or error of a known run |

## Runtime Flow

The frontend posts a message and polls the persisted thread. The worker calls `rag_service POST /query`; it never calls `/resume`. When more incident detail is needed, the backend persists a focused assistant question. The next user message is stored normally, the clarification chain is reconstructed from ordered messages, and a new `/query` is sent with the accumulated context.

Chat is currently single-user and has no authentication or ownership boundary. Deletion is permanent, and deleting a processing thread does not cancel an already-running upstream RAG request.

## Checks

```powershell
cd backend
..\env_mitre\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
..\env_mitre\Scripts\python.exe -m alembic heads
```
