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
*   `/backend/RAG/GraphRAG/` - Core GraphRAG pipeline and evaluation.
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
*   **Test RAG:** `cd backend/RAG/GraphRAG && python main.py --test`

## 5. Common Pitfalls

* **RAG Pathing:** When running RAG scripts, ensure you are in the `/backend/RAG/GraphRAG/` directory. Scripts rely on `__file__` to find `/Documents/`. Running them from the project root will cause `FileNotFoundError`.

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
## 8. Purpose of the Framework

This framework is designed to translate cybercrime investigation records from highly technical language into legally understandable descriptions suitable for prosecutors and legal professionals.

### Problem Context

During cybercrime investigations, law enforcement officers often document technical statements from suspects or digital evidence in raw form, such as:
* *"I exploited port 80"*
* *"I used SQL injection"*
* *"I performed privilege escalation"*

These descriptions are typically accurate from a technical standpoint but are not easily interpretable in a legal context. As a result, prosecutors receiving these case files may struggle to:
*   Understand the technical nature of the attack.
*   Map technical actions to legal charges.
*   Determine the severity and intent of the offense.

### Objective

The objective of this project is to bridge the gap between cybersecurity terminology and legal interpretation by using a web-based LLM interface combined with a Retrieval-Augmented Generation (RAG) pipeline.
### System Architecture

This framework consists of two main modules:

#### 1. Web Application Module (Frontend + Backend)

This module provides the user-facing system and core application logic.

*   **Frontend:**
    *   Provides a web-based interface for users (e.g., prosecutors or investigators).
    *   Allows input of cybercrime case files or technical incident descriptions.
    *   Displays:
        *   Simplified explanations of cyberattacks.
        *   Structured interpretation of technical actions.
        *   Suggested legal mapping outputs.
*   **Backend:**
    *   Handles API requests from the frontend.
    *   Manages authentication and case file processing.
    *   Communicates with the RAG pipeline module.
    *   Aggregates and returns processed results to the frontend.

#### 2. RAG Pipeline Module (Backend Internal Component)

This module is responsible for intelligent interpretation and knowledge retrieval.

*   **Core Functions:**
    *   Receives raw cybercrime technical descriptions from the backend.
    *   Performs retrieval from external knowledge sources (primarily the MITRE ATT&CK framework).
    *   Enriches context using relevant attack techniques, tactics, and procedures (TTPs).
    *   Uses an LLM to generate:
        *   Human-readable explanations of technical actions.
        *   Structured summaries of attack behavior.
        *   Contextual interpretations suitable for legal understanding.

### System Approach

The system:
1.  **Accepts** cybercrime case files containing technical descriptions of attacks.
2.  **Uses** a RAG pipeline to retrieve relevant knowledge from the MITRE ATT&CK framework.
3.  **Translates** technical actions into structured, human-readable explanations.
4.  **Processes** both input and output in the **Thai language**.

### Expected Outcome

The framework enables prosecutors to:
*   Understand cyberattack behavior in plain language.
*   See standardized interpretations of technical actions.