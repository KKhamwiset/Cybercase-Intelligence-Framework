# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CyberCase Intelligence Framework** is a full-stack RAG platform that analyzes cybersecurity incidents using MITRE ATT&CK intelligence and Thai legal documents (Cybersecurity Act, PDPA, Electronic Transactions Acts). It features an agentic pipeline with hybrid retrieval, cross-lingual support (Thai ↔ English), and self-reflection loops.

## Service Layout

The platform is split into three services (see `docker-compose.yml`):

| Service | Path | Port | Role |
|---------|------|------|------|
| Frontend | `frontend/` | 3000 | Next.js UI |
| Backend API | `backend/` | 8000 | FastAPI gateway + PostgreSQL (users, health). Proxies all RAG calls to the RAG service over HTTP (`RAG_SERVICE_URL`) |
| RAG Service | `rag_service/` | 8001 | FastAPI service hosting the GraphRAG pipeline; serves `/query`, `/resume`, `/generate-report`, `/health` |

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
    ├── INSUFFICIENT → ask follow-up (max 2x, returns status=followup)
    └── BROADEN_SEARCH → rewrite queries, loop retrieval
    ↓
[REASONING LLM] Generate English answer
    ↓
[TRANSLATION LLM] Translate to Thai if needed
    ↓
END → AgentResponse(status, answer, followup_question?, session_id?)
```

### API Endpoints

Backend gateway (`backend/app/routers/`, prefix `/api/v1`) — each RAG route proxies to the RAG service:
- `GET /api/v1/health` — System health + DB status
- `POST /api/v1/rag/query` — Query RAG (chain or agent mode via `use_agent`)
- `POST /api/v1/rag/query-file` — Upload a document (PDF/image); Typhoon OCR extracts markdown, then queries RAG in chain mode
- `POST /api/v1/rag/resume` — Resume a paused follow-up session (send `session_id`)
- `POST /api/v1/rag/generate-report` — Generate a structured `CyberCaseReport`

RAG service (`rag_service/app/main.py`, port 8001, no prefix): `GET /health`, `POST /query`, `POST /resume`, `POST /generate-report`.

### Key Modules (under `rag_service/app/RAG/GraphRAG/`)
| Module | Path | Purpose |
|--------|------|---------|
| Agent graph | `pipeline/agent_graph.py` | LangGraph state machine, main pipeline orchestration |
| Hybrid retriever | `retrieval/hybrid_retriever.py` | Vector + graph search with RRF fusion |
| Context builder | `pipeline/context_builder.py` | Format retrieved context for LLM |
| Evaluator | `pipeline/evaluator.py` | Assess context sufficiency, drive self-reflection |
| Report generator | `pipeline/report_generator.py` | Structured `CyberCaseReport` output |
| Config | `config.py` | All RAG settings (models, topK, DB URLs) |
| Ingestion | `ingestion/` | Parse STIX JSON, populate Neo4j + Qdrant |

### Follow-Up Session Flow
When the evaluator returns `INSUFFICIENT`, the API responds with `status: "followup"` and a `session_id`. The frontend must send the user's answer back via `POST /api/v1/rag/resume` with the same `session_id`.

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
- `Documents/` — Thai legal PDFs (Cybersecurity Act, PDPA, Electronic Transactions Act)

## Windows-Specific Notes
- The project is developed on Windows; `rag_service/app/RAG/GraphRAG/main.py` includes UTF-8 encoding fixes for the console
- Use PowerShell syntax for shell commands
