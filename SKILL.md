# TSR Mitre - AI Agent Context & Skills Guide

This document defines the scope, technical stack, and conventions for AI Agents working on the TSR Mitre project. It helps ensure consistency and prevents regressions.


## 1. Project Architecture

The TSR Mitre project is a full-stack web application designed for retrieving and analyzing Thai legal documents (Cybersecurity Act, PDPA, Electronic Transactions Act, etc.) using Retrieval-Augmented Generation (RAG).

**Tech Stack:**
*   **Frontend:** Next.js 15 (App Router, TypeScript, React). Tailwind CSS Modules.
*   **Backend:** FastAPI (Python), running on standard Python runtime.
*   **Database:** PostgreSQL, accessed via **SQLAlchemy** and **Alembic** for migrations.
*   **RAG Engine:** LangChain, LlamaIndex, FAISS, SentenceTransformers, and Anthropic's Claude (Haiku).

## 2. Directory Structure & Ownership

*   `/Documents/` - Contains raw source PDFs. Do not modify these unless explicitly instructed.
*   `/RAG/Python/` - Core RAG scripts (`rag_pipeline.py`, `rag_advanced.py`, etc.).
*   `/RAG/*_index/` - Generated FAISS/BM25 indices. Do not manually edit.
*   `/frontend/` - Next.js application. All UI work happens here.
*   `/backend/` - FastAPI application. All API and database logic happens here.

## 3. Coding Conventions & Constraints

### Python ENV 
* **Activated env:** Ensure the `env_mitre` virtual environment is activated before running backend or RAG commands.

### Frontend (Next.js)
*   **Styling:** Tailwind CSS as Primary, CSS Modules as Secondary
*   **Aesthetics:** Prioritize high-quality, modern UI designs. Use glassmorphism, smooth animations, and dark mode themes as established in the current UI.
*   **State:** Use React hooks. For API calls, use the functions defined in `frontend/src/lib/api.ts`.

### Backend (FastAPI & SQLAlchemy)
*   **FastAPI:** The backend follows standard FastAPI patterns with routers in `app/routers/` and models in `app/models/`.
*   **Alembic:** Use Alembic for database migrations. Run `alembic revision --autogenerate -m "description"` to create migrations and `alembic upgrade head` to apply them.
*   **Validation:** Use Pydantic models for request/response validation.
*   **Configuration:** Use `backend/app/config.py`. Configuration is loaded via `pydantic-settings` from environment variables or a `.env` file.

### RAG Scripts
*   **Pathing:** Scripts use `__file__` to dynamically resolve paths to `/Documents/` and index directories. Do not use hardcoded absolute paths (e.g., `C:\...`).
*   **LLM Provider:** Anthropic Claude is the primary provider. Ensure `ANTHROPIC_API_KEY` is checked before invoking API calls.

## 4. Common Commands

*   **Run Frontend:** `cd frontend && npm run dev`
*   **Run Backend:** `cd backend && uvicorn app.main:app --reload`
*   **Apply Migrations:** `cd backend && alembic upgrade head`
*   **Test RAG:** `cd RAG/Python && python rag_pipeline.py --test`

## 5. Common Pitfalls

* **RAG Pathing:** When running RAG scripts, ensure you are in the `/RAG/Python/` directory. Scripts rely on `__file__` to find `/Documents/`. Running them from the project root will cause `FileNotFoundError`.

* **Alembic Sync:** Always run `alembic upgrade head` after pulling changes that include new migrations.
* **Vector Store Updates:** When updating the vector store with new documents, you must delete the old index directory (e.g., `faiss_index/`) before running the build script again, unless the script is designed to handle incremental updates.

* **Styling Dependencies:** If you encounter errors like `PostCSS error: No PostCSS config found`, ensure that the `postcss`, `tailwindcss`, and `autoprefixer` packages are installed in the frontend dependencies (`package.json`). If missing, run: `cd frontend && npm install postcss tailwindcss autoprefixer`.


## 6. Machine Environment

* **Windows:** All team members use this project on Windows. Bun is installed natively. Do not assume the environment is Linux/Mac. Always use `powershell` or `bash` (via Git Bash or WSL) to run the project.

## 7. Environment Management (Doppler)

We use Doppler for centralized secret management.

*   **Login:** `doppler login` (one-time authentication)
*   **Setup:** `doppler setup` (select project and config for the current directory)
*   **Run with Secrets:** `doppler run -- <your-command>` (injects secrets as environment variables)
*   **Download to .env (Optional):** `doppler secrets download --no-header --format=docker > .env`

**Important:** Never commit `.env` files to Git. Doppler allows us to keep secrets out of the codebase while sharing them across the team.