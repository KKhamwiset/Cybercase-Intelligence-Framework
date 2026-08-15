# AGENTS.md — CyberCase Intelligence Framework

This file provides system architecture, rules, guidelines, and commands for AI coding assistants and developers working on the CyberCase Intelligence Framework repository.

## 🌟 Project Overview
**CyberCase Intelligence Framework** is a chat-focused full-stack Agentic RAG application for cybersecurity incident analysis. It maps threat activity to **MITRE ATT&CK intelligence (STIX 2.1)** and supports persisted chat plus backend-owned clarification. The frontend report view is demo-only, client-side, non-persistent, and unverified; there is no backend case/report workflow. It features:
- Multi-query hybrid retrieval fusing Dense Vector (Qdrant) and Graph Expansion (Neo4j).
- Self-reflection and context-sufficiency loops using LangGraph.
- Cross-lingual support (translating queries from Thai to English and translating reasoning back).
- A single-user chat API backed by PostgreSQL. Authentication and per-user ownership are not implemented.

---

## 🛠️ Tech Stack & Key Configurations
- **Frontend**: Next.js 15 (App Router) + React 19 + Tailwind CSS 4 + TypeScript
- **Backend API**: FastAPI + SQLAlchemy (Async) + PostgreSQL + Alembic
- **Agentic Pipeline**: LangGraph (State Machine) + LangChain LCEL
- **Graph Database**: Neo4j (Enterprise/Community)
- **Vector Database**: Qdrant (1024-dim, BGE-M3 embeddings)
- **Primary LLM Models** (`rag_service/app/RAG/GraphRAG/config.py` & `backend/app/config.py`):
  - **OpenRouter Default**: `qwen/qwen3.8-27b` (alias: `qwen`)
  - **Ready-Selection Aliases**:
    - `qwen` $\to$ `qwen/qwen3.8-27b` (Default)
    - `deepseek` $\to$ `deepseek/deepseek-v4-flash-0731`
    - `sonnet` $\to$ `anthropic/claude-3.5-sonnet`
    - `haiku` $\to$ `anthropic/claude-3.5-haiku`
    - `luna` $\to$ `openai/gpt-5.6-luna`
    - `4o` $\to$ `openai/gpt-4o`
  - **Embedding**: `BAAI/bge-m3` (FP16 on CUDA, FP32 on CPU, 1024-dim)
  - **Reranker**: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
  - **RAGAS Evaluator**: `meta-llama/llama-3.3-70b-instruct:free` (via OpenRouter)

---

## 📂 Key Project Structure & Paths
```
Cybercase Framework/
├── backend/                  # FastAPI chat persistence/orchestration API
│   ├── app/
│   │   ├── main.py           # FastAPI entrypoint
│   │   ├── models/chat.py     # Persisted chat threads, messages, and runs
│   │   ├── routers/           # Health and chat endpoints
│   │   ├── services/chat/     # Chat lifecycle, worker, clarification, RAG client
│   │   ├── services/llm/      # LLM provider routing & model registry
│   │   └── database.py       # Async engine and session management
│   └── alembic/              # Async PostgreSQL migrations
├── rag_service/              # Standalone GraphRAG FastAPI service
│   └── app/RAG/GraphRAG/
│       ├── ingestion/         # Parse STIX JSON and ingest into Neo4j + Qdrant
│       ├── pipeline/          # LangGraph, context builder, and evaluator
│       ├── retrieval/         # Dense + graph retrieval and fusion
│       ├── evaluation/        # RAG evaluation tools
│       ├── model_registry.py  # Central OpenRouter presets & alias resolver
│       └── config.py          # RAG settings and model routing
├── frontend/                 # Next.js 15 Web Application
│   └── src/
│       ├── app/chat/         # Persisted chat workspace
│       └── components/       # Tailwind v4 reusable UI blocks
├── Documents/                # Reference documents and case-analysis knowledge assets
├── Mitre_ATT&CK Doc/         # STIX 2.1 JSON enterprise, mobile, ICS attack patterns
└── docker-compose.yml        # PostgreSQL, backend, rag-service, and frontend
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

# Upgrade the single-head DB migration graph
python -m alembic upgrade head
```

### RAG Pipeline CLI & Interactivity
```bash
cd rag_service/app

# Display available OpenRouter models catalog
python -m RAG.GraphRAG.main --list-models

# Ingest all STIX 2.1 bundle data into Qdrant & Neo4j
python -m RAG.GraphRAG.main --ingest

# Run interactive RAG playground with default DeepSeek model
python -m RAG.GraphRAG.main

# Run with specific model alias (e.g. Sonnet, Qwen, GPT-4o)
python -m RAG.GraphRAG.main --model sonnet
python -m RAG.GraphRAG.main --model qwen
python -m RAG.GraphRAG.main --model 4o

# Run pipeline in LangGraph Agentic mode
python -m RAG.GraphRAG.main --agent

# Run RAGAS metrics evaluation
python -m RAG.GraphRAG.evaluation.eval_runner
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
# Start PostgreSQL, backend, rag-service, and frontend
doppler run -- docker compose up --build
```

---

## 📝 Coding Guidelines & Standards

### Python & FastAPI
1. **Async Everywhere**: Use `async def` and await async DB operations (`SQLAlchemy` or `Motor`/`Redis` calls). Never block the main FastAPI thread.
2. **Type-Safety & Pydantic**: Ensure all incoming requests and response payloads are strictly typed using Pydantic models.
3. **Database Sessions**: Obtain the async DB session through the existing `get_db` FastAPI dependency.

### LangGraph Agentic Loops
1. **State Immutability**: Ensure state updates in `agent_graph.py` return a modified state dictionary instead of modifying keys in-place.
2. **Confidence checks**: The RAG evaluator returns `SUFFICIENT` or `INSUFFICIENT`; an insufficient result selects a bounded recovery strategy such as `BROADEN_SEARCH` or `ACKNOWLEDGE_LIMIT`. It does not pause for user input.
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

### Context Sufficiency And Chat Clarification
- `rag_service` evaluates whether retrieved context is sufficient for a grounded MITRE ATT&CK answer.
- If sufficient, the reasoning model returns the completed technical answer.
- If insufficient, the RAG graph may rewrite and broaden retrieval within its retry budget, then returns the best supported result or acknowledges the limit. It never exposes an interactive `/resume` step to chat.
- Separately, the backend chat worker evaluates the accumulated incident conversation. If a focused clarification is needed, it persists the assistant question. The next answer is persisted as a normal user message, and the backend calls `rag_service POST /query` again with the original incident plus the accumulated clarification exchanges.

### Backend Route Boundary

The backend exposes only `/api/v1/health` and the `/api/v1/chats` thread/message/run routes. Do not add case, report, user, upload/OCR, or standalone RAG-proxy endpoints without an explicit product decision. The frontend Report tab is not evidence that a backend report API exists.
