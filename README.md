# CyberCase Intelligence Framework

CyberCase is an interactive, trust-bounded cyber incident analysis system. It converts unstructured investigator narratives and clarification answers into provenance-aware relational case representations (entities, relationships, evidence candidates, timeline events, missing facts, and explicit uncertainty) while strictly preventing external background knowledge or RAG outputs from contaminating user-reported evidence.

> [!NOTE]
> **Research Scope Division**:
> - **Primary System Scope (This Project / Core Architecture)**: Pre-RAG material-fact clarification, source-bounded trust-boundary fact extraction, relational case representation & visualization, provenance validation, backend service architecture, and empirical representation trade-off evaluation (B0 vs. D1 vs. B2).
> - **External Knowledge Scope (Collaborator/RAG Module)**: External MITRE ATT&CK GraphRAG retrieval (`rag_service/`), hybrid Qdrant vector + Neo4j graph search, and LangGraph self-reflection.

---

## 🌟 Key Architecture & Principles

### 1. Trust-Boundary Principle: "Analytical Knowledge ≠ Case Evidence"
General LLM model knowledge, RAG answers, and MITRE ATT&CK descriptions are **analytical context**, not factual incident evidence. The extraction pipeline ([backend/app/services/extraction/llm_extraction.py](file:///f:/Cybercase%20Framework/backend/app/services/extraction/llm_extraction.py)) strictly restricts its input packet (`ExtractionInput`) to user-authored case messages (`user_case_statement` and `clarification_answer`), excluding RAG outputs to eliminate hallucination contamination.

### 2. Pre-RAG Material-Fact Clarification Gate
Before invoking external knowledge retrieval, the backend clarification policy ([backend/app/services/chat/followup_policy.py](file:///f:/Cybercase%20Framework/backend/app/services/chat/followup_policy.py)) evaluates whether material case facts are missing or ambiguous. It asks up to 3 bounded, concise clarification questions in the user's language or proceeds when context is sufficient or unavailable.

### 3. Provenance-Aware Relational Case Representation
Unstructured text is transformed into an explicit Pydantic JSON schema (`BaselineExtraction`) containing:
- **Entities & Entity-to-Entity Relationships**: Explicitly stated connections with status (`reported`, `suspected`, `contradicted`, `not_established`).
- **Evidence Candidates & Timeline Events**: Incident indicators and chronological actions.
- **Missing Information**: Identified gaps requiring further investigation.
- **Source Message Provenance**: Every extracted item maintains direct binding to user message IDs (`source_message_ids`).

### 4. Empirical Representation Study (B0 vs. D1 vs. B2)
Evaluates intermediate case representations for incident analysis:
- **B0**: Direct report generation (`raw case → report`)
- **D1**: Dehing-adapted summary-first (`raw case → source-preserving text summary → report`)
- **B2**: CyberCase relationship-first (`raw case → structured relational representation → report`)

---

## 🛠️ Tech Stack & Model Routing

- **Frontend**: Next.js 16 (App Router) + React 19 + Tailwind CSS 4 + TypeScript + D3/SVG Graph Rendering
- **Backend**: FastAPI + SQLAlchemy (Async) + PostgreSQL + Alembic
- **Default LLM Routing**: OpenRouter / Anthropic via `openai/gpt-5.6-luna` (configured in `backend/app/config.py`)
- **External RAG**: FastAPI `rag_service` on port 8001 (Qdrant Dense BGE-M3 + Neo4j 2-hop Graph Expansion)

---

## 📂 Services Architecture

```
backend/app/services/
├── __init__.py               # Re-exports domain modules
├── chat/                     # Chat Session Lifecycle, Thread/Message CRUD & Background Worker
│   ├── chat_management.py
│   ├── chat_message.py
│   ├── chat_worker.py
│   ├── followup_policy.py
│   └── rag_client.py
├── llm/                      # Core LLM Provider & Structured Output Infrastructure
│   ├── core_llm.py
│   ├── structured_output.py
│   ├── structured_output_router.py
│   └── structured_output_request_router.py
├── extraction/               # Source-Bounded Fact & Entity/Relationship Extraction
│   ├── llm_extraction.py
│   └── demo_extraction.py
└── reports/                  # Incident Report Generation & PDF Export
    ├── report_service.py
    ├── report_generation.py
    ├── report_prompt.py
    ├── report_provider_schema.py
    └── report_pdf.py
```

---

## 🚀 Quick Start

### Docker Compose

```powershell
doppler run -- docker compose up --build
```

Starts PostgreSQL, backend (port 8000), external RAG service (port 8001), and frontend (port 3000).

Apply PostgreSQL database migrations:
```powershell
cd backend
doppler run -- python -m alembic upgrade head
```

### Local Development

1. **Activate Virtual Environment & Install Dependencies**:
   ```powershell
   .\env_mitre\Scripts\Activate.ps1
   python install_deps.py
   ```

2. **Run Backend API**:
   ```powershell
   cd backend
   doppler run -- python -m alembic upgrade head
   doppler run -- uvicorn app.main:app --port 8000 --reload
   ```

3. **Run Frontend**:
   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

4. Open `http://localhost:3000/chat`. OpenAPI documentation is available at `http://localhost:8000/docs`.

---

## 🧪 Validation & Testing

```powershell
# Backend Pytest Suite (129 tests)
cd backend
..\env_mitre\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
python -m alembic heads

# Frontend Type-check & Production Build
cd frontend
npm run lint
npm run test
npm run build
```
