# TSR Mitre

TSR Mitre is an advanced Retrieval-Augmented Generation (RAG) platform specialized in analyzing and querying Thai legal documents, particularly focusing on the Cybersecurity Act, PDPA, and Electronic Transactions Acts.

It features a modern Next.js frontend, a high-performance FastAPI backend, and leverages powerful vector search and LLM capabilities to provide accurate, cited answers to complex legal queries.

## Project Structure

*   `Documents/`: Source Thai law PDF documents.
*   `rag_service/`: Standalone RAG service with GraphRAG pipelines.
*   `backend/`: FastAPI application providing API endpoints, backed by PostgreSQL and SQLAlchemy. Calls `rag_service` for RAG capabilities.
*   `frontend/`: Next.js 15 web application with a modern dark-theme UI.

## Quick Start

### 1. Environment Setup

#### Python (for RAG and Backend)
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
# This script installs dependencies for both backend and rag_service
python install_deps.py
```

### 2. Environment Management (Doppler)
This project uses **Doppler** to manage environment variables securely. This replaces the need for manual `.env` files.

#### Login & Setup
If you haven't already, authenticate and select the project configuration:
```bash
doppler login
doppler setup
```

#### Running with Secrets
To run any command with environment variables injected:
```bash
doppler run -- <command>
```

### 3. Database Setup
You need a running PostgreSQL database. You can use the provided `docker-compose.yml`:
```bash
docker-compose up -d
```

### 4. RAG Service Setup (FastAPI)
```bash
cd rag_service/app
# Start the RAG service with Doppler secrets
doppler run -- uvicorn main:app --port 8001
```
The RAG service will be available at `http://localhost:8001`.

### 5. Backend Setup (FastAPI)
You don't need a `.env` file if you use Doppler.
```bash
cd backend
# Run migrations using Doppler secrets
doppler run -- alembic upgrade head

# Start the server with Doppler secrets
doppler run -- uvicorn app.main:app --reload
```
The backend will be available at `http://localhost:8000`.

### 6. Frontend Setup
Create a `.env.local` file in the `frontend/` directory.
```bash
cd frontend
npm install
npm run dev
```
The frontend will be available at `http://localhost:3000`.

### 7. RAG CLI Tools
You can also run the RAG pipelines directly via CLI for testing:
```bash
cd rag_service/app/RAG/GraphRAG
python main.py --test
```
*(Requires `ANTHROPIC_API_KEY` to be set in your environment for generation capabilities).*

## Documentation
*   `SKILL.md`: Technical overview and guidelines for AI agents working on the codebase.
