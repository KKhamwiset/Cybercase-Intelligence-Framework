# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CyberCase Intelligence Framework** is a full-stack RAG platform that analyzes cybersecurity incidents using MITRE ATT&CK intelligence and Thai legal documents (Cybersecurity Act, PDPA, Electronic Transactions Acts). It features an agentic pipeline with hybrid retrieval, cross-lingual support (Thai ↔ English), and self-reflection loops.

## Common Commands

### Backend (FastAPI)
```bash
# Activate virtual environment (Windows)
.\env_mitre\Scripts\activate

# Install dependencies for all services
python install_deps.py
```

# Run backend with Doppler secrets
cd backend
doppler run -- uvicorn app.main:app --reload

# Run database migrations
alembic upgrade head
```

### RAG Pipeline (CLI)
```bash
cd backend/RAG/GraphRAG

python main.py --ingest        # Ingest STIX data into Neo4j + Qdrant
python main.py --test          # Run test queries
python main.py                 # Interactive mode
python main.py --agent         # Use LangGraph agentic mode
python main.py --retrieve-only # Debug retrieval only
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
docker-compose up -d   # Start PostgreSQL + all services
```

### RAG Evaluation
```bash
cd backend/RAG/GraphRAG/evaluation
python eval_runner.py  # Run RAGAS-based evaluation metrics
```

## Architecture

### High-Level Stack
- **Frontend**: Next.js 15 + React 19 + Tailwind CSS 4
- **Backend API**: FastAPI + SQLAlchemy (async) + PostgreSQL
- **RAG Engine**: LangGraph (agentic loop) + LangChain LCEL
- **Vector DB**: Qdrant (BGE-M3 embeddings, 1024-dim, FP16)
- **Graph DB**: Neo4j (MITRE ATT&CK STIX entities + relationships)
- **LLMs**: Claude Sonnet 4 (reasoning/translation), Claude Haiku 4.5 (evaluation)

### Agentic RAG Pipeline (`backend/RAG/GraphRAG/pipeline/`)

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

### API Endpoints (`backend/app/routers/`)
- `GET /api/v1/health` — System health + DB status
- `POST /api/v1/rag/query` — Query RAG (chain or agent mode)
- `POST /api/v1/rag/resume` — Resume a paused follow-up session (send `session_id`)

### Key Modules
| Module | Path | Purpose |
|--------|------|---------|
| Agent graph | `pipeline/agent_graph.py` | LangGraph state machine, main pipeline orchestration |
| Hybrid retriever | `retrieval/hybrid_retriever.py` | Vector + graph search with RRF fusion |
| Context builder | `pipeline/context_builder.py` | Format retrieved context for LLM |
| Evaluator | `pipeline/evaluator.py` | Assess context sufficiency, drive self-reflection |
| Config | `RAG/GraphRAG/config.py` | All RAG settings (models, topK, DB URLs) |
| Ingestion | `ingestion/` | Parse STIX JSON, populate Neo4j + Qdrant |

### Follow-Up Session Flow
When the evaluator returns `INSUFFICIENT`, the API responds with `status: "followup"` and a `session_id`. The frontend must send the user's answer back via `POST /api/v1/rag/resume` with the same `session_id`.

## Key Configuration (`backend/RAG/GraphRAG/config.py`)
- **Embedding model**: `BAAI/bge-m3` (1024-dim, FP16)
- **Reranker**: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
- **Reasoning LLM**: `claude-sonnet-4-20250514`
- **Eval LLM**: `claude-haiku-4-5`
- **RAGAS eval LLM**: `meta-llama/llama-3.3-70b-instruct:free` via OpenRouter
- **Vector top-K**: 10, **Graph depth**: 2 hops, **Final top-K**: 5
- **Qdrant collections**: `mitre_entities`, `mitre_relationships`

## Secrets & Environment
- **Doppler** is used for secrets management (replaces `.env` files in deployed environments)
- Local dev can use a `.env` file; backend reads `DATABASE_URL`, `ANTHROPIC_API_KEY`, `NEO4J_*`, `QDRANT_*`
- Deployment targets **Railway** platform via GitHub Actions in `.github/workflows/deploy.yml`

## Data Sources
- `Mitre_ATT&CK Doc/` — STIX 2.1 JSON bundles (enterprise, mobile, ICS attack patterns)
- `Documents/` — Thai legal PDFs (Cybersecurity Act, PDPA, Electronic Transactions Act)

## Windows-Specific Notes
- The project is developed on Windows; `backend/RAG/GraphRAG/main.py` includes UTF-8 encoding fixes for the console
- Use `.\env_mitre\Scripts\activate` (not `source`) for the virtual environment
- Use PowerShell syntax for shell commands
