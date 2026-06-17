# AGENTS.md — CyberCase Intelligence Framework

This file provides system architecture, rules, guidelines, and commands for AI coding assistants and developers working on the CyberCase Intelligence Framework repository.

## 🌟 Project Overview
**CyberCase Intelligence Framework** is an enterprise-grade full-stack Agentic RAG platform designed to analyze cybersecurity incidents. It maps threat activities to **MITRE ATT&CK intelligence (STIX 2.1)** and supports interactive case analysis, evidence-based justification, follow-up questioning, and structured investigation reporting. It features:
- Multi-query hybrid retrieval fusing Dense Vector (Qdrant) and Graph Expansion (Neo4j).
- Self-reflection and context-sufficiency loops using LangGraph.
- Cross-lingual support (translating queries from Thai to English and translating reasoning back).

---

## 🛠️ Tech Stack & Key Configurations
- **Frontend**: Next.js 15 (App Router) + React 19 + Tailwind CSS 4 + TypeScript
- **Backend API**: FastAPI + SQLAlchemy (Async) + PostgreSQL + Alembic
- **Agentic Pipeline**: LangGraph (State Machine) + LangChain LCEL
- **Graph Database**: Neo4j (Enterprise/Community)
- **Vector Database**: Qdrant (1024-dim, BGE-M3 embeddings)
- **Primary LLM Models** (`RAG/GraphRAG/config.py`):
  - **Reasoning**: `claude-sonnet-4-20250514` (or latest Sonnet)
  - **Evaluator / Token-efficiency**: `claude-haiku-4-5`
  - **Embedding**: `BAAI/bge-m3` (FP16, 1024-dim)
  - **Reranker**: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
  - **RAGAS Evaluator**: `meta-llama/llama-3.3-70b-instruct:free` (via OpenRouter)

---

## 📂 Key Project Structure & Paths
```
Cybercase Framework/
├── backend/                  # FastAPI Backend API
│   ├── app/
│   │   ├── main.py           # FastAPI entrypoint
│   │   ├── models/           # SQLAlchemy models (async pg)
│   │   ├── routers/          # API endpoints (RAG queries & sessions)
│   │   └── database.py       # Async engine and session management
│   ├── RAG/GraphRAG/         # Agentic RAG Pipeline Engine
│   │   ├── ingestion/        # Parse STIX JSON & ingest into Neo4j + Qdrant
│   │   │   └── ingest_stix.py
│   │   ├── pipeline/
│   │   │   ├── agent_graph.py     # LangGraph state machine flow
│   │   │   ├── context_builder.py # context formatting for reasoning
│   │   │   └── evaluator.py       # Sufficiency assessment (case facts / technical)
│   │   ├── retrieval/
│   │   │   └── hybrid_retriever.py # Qdrant dense vector + Neo4j 2-hop search
│   │   ├── evaluation/       # RAGAS metric evaluations
│   │   └── config.py         # Global configuration, thresholds, model routing
│   └── alembic/              # Async PostgreSQL migrations
├── frontend/                 # Next.js 15 Web Application
│   └── src/
│       ├── app/              # App router (dashboard, incident analyzer, chat)
│       └── components/       # Tailwind v4 reusable UI blocks
├── Documents/                # Reference documents and case-analysis knowledge assets
├── Mitre_ATT&CK Doc/         # STIX 2.1 JSON enterprise, mobile, ICS attack patterns
└── docker-compose.yml        # Docker setup (PostgreSQL, PgAdmin, Neo4j, Qdrant)
```

---

## 💻 Common Commands

### Virtual Environment & Backend Setup (Windows)
```bash
# Activate virtual environment (Windows MSYS Bash / Git Bash)
source env_mitre/Scripts/activate  # Or in Cmd/PowerShell: .\env_mitre\Scripts\activate

# Install dependencies for all services
python install_deps.py

# Run FastAPI backend with Doppler secret management
cd backend
doppler run -- uvicorn app.main:app --reload

# Upgrade DB Schema using Alembic migrations
alembic upgrade head
```

### RAG Pipeline CLI & Interactivity
```bash
cd backend/RAG/GraphRAG

# Ingest all STIX 2.1 bundle data into Qdrant & Neo4j
python main.py --ingest

# Run interactive RAG playground
python main.py

# Run pipeline in LangGraph Agentic mode
python main.py --agent

# Run RAGAS metrics evaluation
cd evaluation
python eval_runner.py
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev     # Run Dev server on http://localhost:3000
npm run lint    # ESLint checking
npm run build   # Production compile
```

### Docker Infrastructure
```bash
# Spin up databases and admin panels in the background
docker-compose up -d
```

---

## 📝 Coding Guidelines & Standards

### Python & FastAPI
1. **Async Everywhere**: Use `async def` and await async DB operations (`SQLAlchemy` or `Motor`/`Redis` calls). Never block the main FastAPI thread.
2. **Type-Safety & Pydantic**: Ensure all incoming requests and response payloads are strictly typed using Pydantic models.
3. **Database Sessions**: Obtain the DB session async via dependency injection: `async for db in get_db_session()`.

### LangGraph Agentic Loops
1. **State Immutability**: Ensure state updates in `agent_graph.py` return a modified state dictionary instead of modifying keys in-place.
2. **Confidence checks**: The `evaluator.py` must return either `SUFFICIENT`, `INSUFFICIENT`, or `BROADEN_SEARCH`. If `INSUFFICIENT`, output an engaging `followup_question`.
3. **Grace Limit**: Limit loop iterations strictly. Never let self-reflection run for more than 2-3 iterations to avoid infinite API cost.

### Next.js & React
1. **React 19 & Tailwind v4**: Use utility-first styling with native Tailwind v4 class names. Use React 19 primitives.
2. **Strict TypeScript**: Avoid `any`. Define interfaces for all props, states, and API return values.

---

## 🔄 Ingestion & RAG Core Pipelines

### The Hybrid Retrieval System
The `hybrid_retriever.py` queries Qdrant vectors and retrieves matching nodes from the Neo4j Graph DB:
1. **Dense Vector Search**: Embeds query using `BAAI/bge-m3` → matches vectors in Qdrant with cosine similarity.
2. **Graph Expansion**: Performs 2-hop depth Cypher queries in Neo4j to pull associated techniques, sub-techniques, software, and mitigations.
3. **Fusion (RRF)**: Merges results using Reciprocal Rank Fusion to compile context that is fed to `context_builder.py`.

### Context Sufficiency Flow (Evaluator)
- Evaluates if the context retrieved contains enough incident facts to support MITRE ATT&CK mapping and report generation.
- If **Sufficient** → Reasoning model outputs final technical analysis and structured investigation brief.
- If **Insufficient** → Backend stores session states in PostgreSQL, raises `status: "followup"`, asks user a clarification question, and awaits `POST /api/v1/rag/resume` with `session_id`.
