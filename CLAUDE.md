# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CyberCase Intelligence Framework** is a chat-focused full-stack RAG application that analyzes cybersecurity incidents using MITRE ATT&CK intelligence. It features an agentic pipeline with hybrid retrieval, cross-lingual support (Thai ↔ English), and self-reflection loops. Persistent interactive clarification lives in the backend chat workflow; the RAG service itself never pauses. The frontend Report tab is a demo-only, client-side, non-persistent, unverified view, not a backend report workflow.

## Service Layout

The platform is split into three services (see `docker-compose.yml`):

| Service | Path | Port | Role |
|---------|------|------|------|
| Frontend | `frontend/` | 3000 | Next.js UI |
| Backend API | `backend/` | 8000 | FastAPI chat persistence/orchestration + PostgreSQL. The chat worker calls the RAG service over HTTP (`RAG_SERVICE_URL`) |
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
python -m RAG.GraphRAG.main                 # Interactive mode (agent)
python -m RAG.GraphRAG.main --retrieve-only # Debug retrieval only
python -m RAG.GraphRAG.main --fast          # Single retrieve → one answer call
python -m RAG.GraphRAG.main --ultrafast     # Vector-only retrieve → terse answer
```
The CLI has no `--local` flag — Ollama is offline-tooling only, see RAG Evaluation
below. `--agent` still parses but is a no-op: the agent is the only pipeline.

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
- **Backend API**: FastAPI + SQLAlchemy (async) + PostgreSQL — owns chat threads/messages/runs, background work, and clarification policy; calls the RAG service via HTTPX
- **RAG Engine**: LangGraph for orchestration (the agentic state machine) plus LangChain for the LLM and message abstractions (`langchain_core.messages`, `langchain_anthropic.ChatAnthropic`), hosted in `rag_service`. LangGraph is a separate library, not part of LangChain. No LCEL — the LCEL chain is evaluation-only (`pipeline/chain.py`)
- **Vector DB**: Qdrant (BGE-M3 embeddings, 1024-dim, FP16)
- **Graph DB**: Neo4j (MITRE ATT&CK STIX entities + relationships)
- **LLMs**: one `CORE_LLM_PROVIDER` drives reasoning, routing, decomposition and evaluation. Default is `openrouter` → `openai/gpt-5.6-luna`; set `CORE_LLM_PROVIDER=anthropic` for `claude-haiku-4-5`. The served pipeline is cloud-only

### Agentic RAG Pipeline (`rag_service/app/RAG/GraphRAG/pipeline/`)

The pipeline is a LangGraph state machine in `agent_graph.py`:

```
User Input (Thai/English)
    ↓
[ROUTER] Classifies, but the result is currently discarded — the graph edge is
    hard-wired to the incident path, so general-explanation is unreachable
    ↓
[PREPARE] Detect response language only. NO input translation — BGE-M3 is
    multilingual and retrieves on the Thai text as-is
    ↓
[DECOMPOSE] Incident → atomic per-technique sub-queries, in the incident's
    own language (query_decomposer.py)
    ↓
[HYBRID RETRIEVAL] retrieve_multi_quota — per-query quota, round-robin
    interleaved so every sub-query's technique survives the trim
    ├── Dense vector search (Qdrant + BGE-M3) + rerank
    └── Graph expansion (Neo4j, 2 hops)
    ↓
[EVALUATOR] Context sufficiency check (evaluator.py)
    ├── SUFFICIENT → proceed
    └── INSUFFICIENT → BROADEN_SEARCH: the agent rewrites the query itself and
        loops retrieval (max 2x). Budget spent → answer with the best context
        available, or return the evaluator's ACKNOWLEDGE_LIMIT message.
    ↓
[REASONING LLM] Generate answer (single-call Thai by default)
    ↓
[TRANSLATION LLM] Skipped on the normal Thai path (single-call already wrote
    Thai). Still runs for an ACKNOWLEDGE_LIMIT message, and for the whole
    answer if SINGLE_CALL_GENERATION=false
    ↓
END → AgentResponse(status="completed", answer)
```

The pipeline never pauses for user input.

### API Endpoints

Backend (`backend/app/routers/`, prefix `/api/v1`) exposes only the health and persistent-chat boundary:
- `GET /api/v1/health` — backend and database health
- `GET`, `POST /api/v1/chats` — list or create chat threads
- `GET`, `PATCH`, `DELETE /api/v1/chats/{thread_id}` — read, rename, or permanently delete one thread
- `POST /api/v1/chats/{thread_id}/messages` — persist a user message and enqueue a background run (`202`)
- `GET /api/v1/chats/{thread_id}/runs/{run_id}` — inspect a known run's status/error

There are no backend case, report, user, upload/OCR, or standalone RAG-proxy routes. Chat is currently single-user and has no authentication or ownership boundary.

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

### Chat Clarification Boundary

The backend owns bounded clarification in `backend/app/services/chat/`. A user answer is stored as a normal chat message. The backend reconstructs the active clarification chain from ordered persisted messages and issues another RAG `POST /query` containing the original incident plus accumulated question/answer context. The chat path never calls RAG `/resume`, and the frontend never calls `rag_service` directly.

The frontend may derive an extraction and seven-section report from the selected persisted thread. The report is assembled in the browser, is not separately persisted, and must remain visibly demo-only and unverified unless a new backend contract is explicitly approved.
## Key Configuration (`rag_service/app/RAG/GraphRAG/config.py`)
- **Embedding model**: `BAAI/bge-m3` (1024-dim, FP16)
- **Reranker**: `BAAI/bge-reranker-v2-m3` (multilingual incl. Thai)
- **Core LLM**: `CORE_LLM_PROVIDER` (`openrouter` default → `openai/gpt-5.6-luna`, or `anthropic` → `claude-haiku-4-5`) — used for reasoning, routing, decomposition and evaluation
- **Single-call generation**: `SINGLE_CALL_GENERATION=true` — Thai answers are written in one call; set false to restore reason-EN-then-translate
- **`DUAL_QUERY_RETRIEVAL`**: read only by `pipeline/chain.py`, which is evaluation-only. The served agent does no input translation
- **RAGAS eval LLM**: `qwen/qwen-2.5-72b-instruct` via OpenRouter
- **Local models (`evaluation/` only)**: Ollama `qwen2.5:7b` + `gemma3:4b`, `OLLAMA_BASE_URL` (default `http://localhost:11434`). Not reachable from the service
- **Vector top-K**: 10, **Graph depth**: 2 hops, **Final top-K**: 5
- **Qdrant collections**: `mitre_entities`, `mitre_relationships`

## Secrets & Environment
- **Doppler** is used for secrets management (replaces `.env` files in deployed environments); local dev can use `.env` files
- Backend runtime and online migrations read `POSTGRES_*`; chat also reads `RAG_SERVICE_URL` and `ANTHROPIC_API_KEY`
- RAG service reads `ANTHROPIC_API_KEY`, `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD`, `QDRANT_URL`/`QDRANT_API_KEY`, `OPENROUTER_API_KEY`
- Deployment targets **Railway** platform via GitHub Actions in `.github/workflows/deploy.yml`

## Data Sources
- `Mitre_ATT&CK Doc/` — STIX 2.1 JSON bundles (enterprise, mobile, ICS attack patterns)
- `Documents/` — reference documents and case-analysis knowledge assets

## Windows-Specific Notes
- The project is developed on Windows; `rag_service/app/RAG/GraphRAG/main.py` includes UTF-8 encoding fixes for the console
- Use PowerShell syntax for shell commands
