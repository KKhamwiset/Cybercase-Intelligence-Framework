# TSR Mitre - AI Agent Context & Skills Guide

This document defines the scope, technical stack, and conventions for AI Agents working on the TSR Mitre project. It helps ensure consistency and prevents regressions.

## 1. Project Architecture

The TSR Mitre project is a full-stack web application designed for retrieving and analyzing Thai legal documents (Cybersecurity Act, PDPA, Electronic Transactions Act, etc.) using Retrieval-Augmented Generation (RAG).

**Tech Stack:**
*   **Frontend:** Next.js 15 (App Router, TypeScript, React). Tailwind CSS Modules.
*   **Backend:** FastAPI (Python), providing REST APIs.
*   **Database:** PostgreSQL, accessed via SQLAlchemy (async with `asyncpg`) and managed by Alembic.
*   **RAG Engine:** LangChain, LlamaIndex, FAISS, SentenceTransformers, and Anthropic's Claude (Haiku).

## 2. Directory Structure & Ownership

*   `/Documents/` - Contains raw source PDFs. Do not modify these unless explicitly instructed.
*   `/RAG/Python/` - Core RAG scripts (`rag_pipeline.py`, `rag_advanced.py`, etc.).
*   `/RAG/Jupyter/` - Sandbox notebooks for experimentation.
*   `/RAG/*_index/` - Generated FAISS/BM25 indices. Do not manually edit.
*   `/frontend/` - Next.js application. All UI work happens here.
*   `/backend/` - FastAPI application. All API and database logic happens here.

## 3. Coding Conventions & Constraints

### Frontend (Next.js)
*   **Styling:** Use standard CSS Modules (`.module.css`). **Do not use Tailwind CSS** unless explicitly instructed by the user. Follow the existing design system tokens defined in `frontend/src/app/globals.css`.
*   **Aesthetics:** Prioritize high-quality, modern UI designs. Use glassmorphism, smooth animations, and dark mode themes as established in the current UI.
*   **State:** Use React hooks. For API calls, use the functions defined in `frontend/src/lib/api.ts`.

### Backend (FastAPI & SQLAlchemy)
*   **Async First:** The database uses `asyncpg` and `AsyncSession`. Ensure all database queries are awaited.
*   **Alembic:** Any changes to SQLAlchemy models in `backend/app/models/` must be followed by an Alembic migration (`alembic revision --autogenerate -m "..."`).
*   **Configuration:** Use `pydantic-settings` (`backend/app/config.py`). Sensitive keys (like `ANTHROPIC_API_KEY` or `DATABASE_URL`) must be loaded from `.env` and never hardcoded.

### RAG Scripts
*   **Pathing:** Scripts use `__file__` to dynamically resolve paths to `/Documents/` and index directories. Do not use hardcoded absolute paths (e.g., `C:\...`).
*   **LLM Provider:** Anthropic Claude is the primary provider. Ensure `ANTHROPIC_API_KEY` is checked before invoking API calls.

## 4. Common Commands

*   **Run Frontend:** `cd frontend && npm run dev`
*   **Run Backend:** `cd backend && uvicorn app.main:app --reload`
*   **Run Migrations:** `cd backend && alembic upgrade head`
*   **Test RAG:** `cd RAG/Python && python rag_pipeline.py --test`

## 5. Common Pitfalls

* **RAG Pathing:** When running RAG scripts, ensure you are in the `/RAG/Python/` directory. Scripts rely on `__file__` to find `/Documents/`. Running them from the project root will cause `FileNotFoundError`.

* **Alembic Migrations:** Always run `alembic upgrade head` after modifying models. If the migration doesn't detect changes, manually create one: `alembic revision --autogenerate -m "Description of changes"`.
* **Vector Store Updates:** When updating the vector store with new documents, you must delete the old index directory (e.g., `faiss_index/`) before running the build script again, unless the script is designed to handle incremental updates.

* **Styling Dependencies:** If you encounter errors like `PostCSS error: No PostCSS config found`, ensure that the `postcss`, `tailwindcss`, and `autoprefixer` packages are installed in the frontend dependencies (`package.json`). If missing, run: `cd frontend && npm install postcss tailwindcss autoprefixer`.
