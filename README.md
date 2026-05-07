# TSR Mitre

TSR Mitre is an advanced Retrieval-Augmented Generation (RAG) platform specialized in analyzing and querying Thai legal documents, particularly focusing on the Cybersecurity Act, PDPA, and Electronic Transactions Acts.

It features a modern Next.js frontend, a high-performance ElysiaJS backend running on Bun, and leverages powerful vector search and LLM capabilities to provide accurate, cited answers to complex legal queries.

## Project Structure

*   `Documents/`: Source Thai law PDF documents.
*   `RAG/`: Core retrieval and generation pipelines using LangChain, LlamaIndex, and FAISS.
*   `frontend/`: Next.js 15 web application with a modern dark-theme UI.
*   `backend/`: ElysiaJS application (Bun runtime) providing API endpoints, backed by PostgreSQL and Prisma ORM.

## Quick Start

### 1. Environment Setup

#### Python (for RAG CLI tools)
Create a virtual environment to manage Python dependencies:
```bash
# In the project root directory
python -m venv env_mitre
```

Activate the virtual environment:
*   **Windows:** `.\env_mitre\Scripts\activate`
*   **macOS/Linux:** `source env_mitre/bin/activate`

Install the required Python packages:
```bash
pip install -r requirements.txt
```

#### Bun (for Backend)
The backend requires the **Bun** runtime. If you don't have it installed on Windows, run:
```powershell
powershell -c "irm bun.sh/install.ps1 | iex"
```

### 2. Database Setup
You need a running PostgreSQL database. You can use the provided `docker-compose.yml`:
```bash
docker-compose up -d
```

### 3. Backend Setup (ElysiaJS)
Create a `.env` file in the `backend/` directory (see `.env` example).
```bash
cd backend
bun install
npx prisma generate
bun run dev
```
The backend will be available at `http://localhost:8000`.

### 4. Frontend Setup
Create a `.env.local` file in the `frontend/` directory (see `.env.local.example`).
```bash
cd frontend
npm install
npm run dev
```
The frontend will be available at `http://localhost:3000`.

### 4. RAG CLI Tools
You can also run the RAG pipelines directly via CLI for testing:
```bash
cd RAG/Python
python rag_pipeline.py --test
```
*(Requires `ANTHROPIC_API_KEY` to be set in your environment for generation capabilities).*

## Documentation
*   `SKILL.md`: Technical overview and guidelines for AI agents working on the codebase.
