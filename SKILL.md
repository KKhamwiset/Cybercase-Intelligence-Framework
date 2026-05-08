# TSR Mitre - AI Agent Context & Skills Guide

This document defines the scope, technical stack, and conventions for AI Agents working on the TSR Mitre project. It helps ensure consistency and prevents regressions.


## 1. Project Architecture

The TSR Mitre project is a full-stack web application designed for retrieving and analyzing Thai legal documents (Cybersecurity Act, PDPA, Electronic Transactions Act, etc.) using Retrieval-Augmented Generation (RAG).

**Tech Stack:**
*   **Frontend:** Next.js 15 (App Router, TypeScript, React). Tailwind CSS Modules.
*   **Backend:** ElysiaJS (TypeScript), running on the **Bun** runtime.
*   **Database:** PostgreSQL, accessed via **Prisma ORM**.
*   **RAG Engine:** LangChain, LlamaIndex, FAISS, SentenceTransformers, and Anthropic's Claude (Haiku).

## 2. Directory Structure & Ownership

*   `/Documents/` - Contains raw source PDFs. Do not modify these unless explicitly instructed.
*   `/RAG/Python/` - Core RAG scripts (`rag_pipeline.py`, `rag_advanced.py`, etc.).
*   `/RAG/Jupyter/` - Sandbox notebooks for experimentation.
*   `/RAG/*_index/` - Generated FAISS/BM25 indices. Do not manually edit.
*   `/frontend/` - Next.js application. All UI work happens here.
*   `/backend/` - ElysiaJS application. All API and database logic happens here.

## 3. Coding Conventions & Constraints

### Python ENV 
* **Activated env:** If the env folder is persist make sure to activated it first before further running a command else run the command via global script.

### Frontend (Next.js)
*   **Styling:** Tailwind CSS as Primary, CSS Modules as Secondary
*   **Aesthetics:** Prioritize high-quality, modern UI designs. Use glassmorphism, smooth animations, and dark mode themes as established in the current UI.
*   **State:** Use React hooks. For API calls, use the functions defined in `frontend/src/lib/api.ts`.

### Backend (ElysiaJS & Prisma)
*   **Bun Runtime:** The backend runs exclusively on Bun. Use `bun` commands for package management and running scripts.
*   **Prisma:** Any changes to the database schema in `backend/prisma/schema.prisma` must be followed by client generation (`npx prisma generate`) and database sync (`npx prisma db push`).
*   **Validation:** Use Elysia's native `t` (TypeBox) object for strict request/response validation in routes.
*   **Configuration:** Use `backend/src/config.ts`. Sensitive keys must be loaded from `.env` and never hardcoded.

### RAG Scripts
*   **Pathing:** Scripts use `__file__` to dynamically resolve paths to `/Documents/` and index directories. Do not use hardcoded absolute paths (e.g., `C:\...`).
*   **LLM Provider:** Anthropic Claude is the primary provider. Ensure `ANTHROPIC_API_KEY` is checked before invoking API calls.

## 4. Common Commands

*   **Install Bun (Windows):** `powershell -c "irm bun.sh/install.ps1 | iex"`
*   **Run Frontend:** `cd frontend && npm run dev`
*   **Run Backend:** `cd backend && bun run dev`
*   **Generate Prisma Client:** `cd backend && npx prisma generate`
*   **Sync DB Schema:** `cd backend && npx prisma db push`
*   **Test RAG:** `cd RAG/Python && python rag_pipeline.py --test`

## 5. Common Pitfalls

* **RAG Pathing:** When running RAG scripts, ensure you are in the `/RAG/Python/` directory. Scripts rely on `__file__` to find `/Documents/`. Running them from the project root will cause `FileNotFoundError`.

* **Prisma Sync:** Always run `npx prisma generate` after modifying `schema.prisma`. If you need to push changes to the database during development, use `npx prisma db push`.
* **Vector Store Updates:** When updating the vector store with new documents, you must delete the old index directory (e.g., `faiss_index/`) before running the build script again, unless the script is designed to handle incremental updates.

* **Styling Dependencies:** If you encounter errors like `PostCSS error: No PostCSS config found`, ensure that the `postcss`, `tailwindcss`, and `autoprefixer` packages are installed in the frontend dependencies (`package.json`). If missing, run: `cd frontend && npm install postcss tailwindcss autoprefixer`.


## 6. Machine Environment

* **Windows:** All team members use this project on Windows. Bun is installed natively. Do not assume the environment is Linux/Mac. Always use `powershell` or `bash` (via Git Bash or WSL) to run the project.

## 7. Login to env

* `doppler login`
* `doppler setup`
* `doppler run --command="echo \$env_tsr_mitre"`

##