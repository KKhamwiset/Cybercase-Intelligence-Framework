# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CyberCase Intelligence Framework** is a full-stack RAG platform that analyzes cybersecurity incidents using MITRE ATT&CK intelligence. It features an agentic pipeline with hybrid retrieval, cross-lingual support (Thai ↔ English), and self-reflection loops. Interactive follow-up handling lives in the Backend case-analysis workflow — the RAG service itself never pauses.

## Service Layout

The platform is split into three services (see `docker-compose.yml`):

| Service | Path | Port | Role |
|---------|------|------|------|
| Frontend | `frontend/` | 3000 | Next.js UI |
| Backend API | `backend/` | 8000 | FastAPI gateway + PostgreSQL (users, health). Proxies all RAG calls to the RAG service over HTTP (`RAG_SERVICE_URL`) |
| RAG Service | `rag_service/` | 8001 | FastAPI service hosting the GraphRAG pipeline; serves `/query`, `/health`, `/retrieval-contexts/{id}` |

The RAG pipeline code lives at `rag_service/app/RAG/GraphRAG/` (it was migrated out of `backend/` — backend no longer contains any RAG code). `rag_service/finetune/` holds the MITRE ATT&CK specialist fine-tune module (cloud QLoRA training + A/B compare; see its `README.md`).

## Common Commands

### Install Dependencies
```bash
# Installs backend/requirements.txt + rag_service/requirements.txt into the active Python
python install_deps.py
```

### Backend API (FastAPI, port 8000)
```bash
cd backend
doppler run -- uvicorn app.main:app --reload   # with Doppler secrets
# or with a local .env file:
uvicorn app.main:app --reload

# Run database migrations
python -m alembic upgrade head
```

### RAG Service (FastAPI, port 8001)
```bash
cd rag_service
uvicorn app.main:app --port 8001 --reload
```
Startup loads BGE-M3 + reranker models once and connects to Neo4j/Qdrant — first boot is slow.

### RAG Pipeline (CLI)
The CLI must be run as a module from `rag_service/app` (the code uses relative imports — `python main.py` will not work):
```bash
cd rag_service/app

python -m RAG.GraphRAG.main --ingest        # Ingest STIX data into Neo4j + Qdrant
python -m RAG.GraphRAG.main --test          # Run test queries
python -m RAG.GraphRAG.main                 # Interactive mode
python -m RAG.GraphRAG.main --agent         # Use LangGraph agentic mode
python -m RAG.GraphRAG.main --retrieve-only # Debug retrieval only
python -m RAG.GraphRAG.main --agent --local # Use local Ollama models instead of Claude
```
Note: `--ingest` resolves the STIX data dir from `config.py` `_PROJECT_ROOT`, which currently points at `rag_service/` — but the STIX bundles live at the repo root (`Mitre_ATT&CK Doc/`). Check this path before running ingestion.

### RAG Evaluation
```bash
cd rag_service/app/RAG/GraphRAG

python -m evaluation.eval_runner --dataset evaluation/eval_dataset.json --mode retriever
python -m evaluation.eval_runner --dataset evaluation/eval_dataset.json --mode generation
python -m evaluation.eval_runner --dataset evaluation/eval_dataset.json --mode full
# Options: --local (Ollama models), --output results.md, --max-samples N
```

### Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev    # Development server on http://localhost:3000
npm run lint   # ESLint
npm run build  # Production build
```

### Docker
```bash
doppler run -- docker compose up --build   # PostgreSQL (host port 5433) + backend + rag-service + frontend
```
Neo4j and Qdrant are cloud-hosted — no local containers for them.

## Architecture

### High-Level Stack
- **Frontend**: Next.js 15 + React 19 + Tailwind CSS 4
- **Backend API**: FastAPI + SQLAlchemy (async) + PostgreSQL — thin gateway, calls RAG service via httpx
- **RAG Engine**: LangGraph (agentic loop) + LangChain LCEL, hosted in `rag_service`
- **Vector DB**: Qdrant (BGE-M3 embeddings, 1024-dim, FP16)
- **Graph DB**: Neo4j (MITRE ATT&CK STIX entities + relationships)
- **LLMs**: Claude Sonnet 4 (reasoning/translation), Claude Haiku 4.5 (evaluation); optional local Ollama mode (`--local`)
- **OCR**: Typhoon OCR for document uploads (`/rag/query-file`)

### Agentic RAG Pipeline (`rag_service/app/RAG/GraphRAG/pipeline/`)

The pipeline is a LangGraph state machine in `agent_graph.py`:

```
User Input (Thai/English)
    ↓
[ROUTER] General explanation? → Direct LLM → END
    ↓ (Incident analysis path)
[CROSS-LINGUAL] Translate query to English
    ↓
[HYBRID RETRIEVAL] Multi-query (hybrid_retriever.py)
    ├── Dense vector search (Qdrant + BGE-M3)
    └── Graph expansion (Neo4j, 2-hop depth)
    ↓
[EVALUATOR] Context sufficiency check (evaluator.py)
    ├── SUFFICIENT → proceed
    └── INSUFFICIENT → BROADEN_SEARCH: the agent rewrites the query itself and
        loops retrieval (max 2x). Budget spent → answer with the best context
        available, or return the evaluator's ACKNOWLEDGE_LIMIT message.
    ↓
[REASONING LLM] Generate answer (single-call Thai by default)
    ↓
[TRANSLATION LLM] Translate to Thai if needed (skipped for single-call)
    ↓
END → AgentResponse(status="completed", answer)
```

The pipeline never pauses for user input.

### API Endpoints

Backend gateway (`backend/app/routers/`, prefix `/api/v1`) — query routes proxy to the RAG service, report routes are handled locally by the Backend `ReportWorkflowService`:
- `GET /api/v1/health` — System health + DB status
- `POST /api/v1/rag/query` — Query RAG (chain or agent mode via `use_agent`)
- `POST /api/v1/rag/query-file` — Upload a document (PDF/image); Typhoon OCR extracts markdown, then queries RAG in chain mode
- `POST /api/v1/cases/{case_id}/report` — Start RAG-driven report generation for a case
- `POST /api/v1/cases/{case_id}/report/resume` — Resume report follow-up session
- `GET /api/v1/cases/{case_id}/report` — Get latest report for a case
- `GET /api/v1/reports` — List all persisted reports registry summaries
- `GET /api/v1/reports/{report_id}` — Get report details
- `PATCH /api/v1/reports/{report_id}/review-status` — Update report review status

RAG service (`rag_service/app/main.py`, port 8001, no prefix): `GET /health`, `POST /query`, `GET /retrieval-contexts/{context_id}`.

### Key Modules (under `rag_service/app/RAG/GraphRAG/`)
| Module | Path | Purpose |
|--------|------|---------|
| Agent graph | `pipeline/agent_graph.py` | LangGraph state machine, main pipeline orchestration |
| Hybrid retriever | `retrieval/hybrid_retriever.py` | Vector + graph search with RRF fusion |
| Context builder | `pipeline/context_builder.py` | Format retrieved context for LLM |
| Evaluator | `pipeline/evaluator.py` | Assess context sufficiency, drive self-reflection |

| Config | `config.py` | All RAG settings (models, topK, DB URLs) |
| Ingestion | `ingestion/` | Parse STIX JSON, populate Neo4j + Qdrant |

### Follow-Up Handling (moved out of the RAG service, 2026-07-28)
The RAG service's follow-up module (pause → ask → `POST /resume`) was removed; `GraphRAGAgent.query()` always returns `status: "completed"`. Interactive clarification belongs to the Backend case-analysis workflow (`app/services/report_workflow.py`, `app/services/case_chat.py`), which asks its own questions, persists the answers on the case, and re-queries `POST /query` with the enriched incident text. See `rag_service/docs/FOLLOWUP_REMOVAL.md`.

⚠️ `CaseChatService.send_message(action="followup")` still calls the RAG service `/resume` directly (`backend/app/services/case_chat.py:607`). That call now 404s, which the service already maps to `status="expired"` — the chat follow-up action is inert until reimplemented Backend-side.

### Report Workflow States
The report generator endpoints return one of these three precise response states:
1. `completed`: contains `report_id`, `report`, and optional rendered `answer`.
2. `followup`: only for a real incomplete report; includes a valid stored `session_id`; can be resumed through the backend workflow.
3. `context_expired`: returned when `retrieval_context_id` is missing, expired, or unavailable (includes `error_code: "retrieval_context_expired"` and a user-facing message instructing the caller to rerun RAG analysis). This state deliberately contains no `session_id` and is not resumable.
## Key Configuration (`rag_service/app/RAG/GraphRAG/config.py`)
- **Embedding model**: `BAAI/bge-m3` (1024-dim, FP16)
- **Reranker**: `BAAI/bge-reranker-v2-m3` (multilingual incl. Thai)
- **Dual-query retrieval**: `DUAL_QUERY_RETRIEVAL=true` — Thai queries are retrieved both as-is and via English translation, results fused
- **Reasoning LLM**: `claude-sonnet-4-20250514`
- **Eval LLM**: `claude-haiku-4-5`
- **RAGAS eval LLM**: `qwen/qwen-2.5-72b-instruct` via OpenRouter
- **Local mode (`--local`)**: Ollama `qwen2.5:7b` (pipeline) + `gemma3:4b` (eval/RAGAS judge), `OLLAMA_BASE_URL` (default `http://localhost:11434`)
- **Vector top-K**: 10, **Graph depth**: 2 hops, **Final top-K**: 5
- **Qdrant collections**: `mitre_entities`, `mitre_relationships`

## Secrets & Environment
- **Doppler** is used for secrets management (replaces `.env` files in deployed environments); local dev can use `.env` files
- Backend reads `DATABASE_URL` (or `POSTGRES_*`), `RAG_SERVICE_URL`, `ANTHROPIC_API_KEY`, `TYPHOON_OCR_API_KEY`/`TYPHOON_API_KEY`
- RAG service reads `ANTHROPIC_API_KEY`, `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD`, `QDRANT_URL`/`QDRANT_API_KEY`, `OPENROUTER_API_KEY`
- Deployment targets **Railway** platform via GitHub Actions in `.github/workflows/deploy.yml`

## Data Sources
- `Mitre_ATT&CK Doc/` — STIX 2.1 JSON bundles (enterprise, mobile, ICS attack patterns)
- `Documents/` — reference documents and case-analysis knowledge assets

## Windows-Specific Notes
- The project is developed on Windows; `rag_service/app/RAG/GraphRAG/main.py` includes UTF-8 encoding fixes for the console
- Use PowerShell syntax for shell commands
