# CyberCase Chat, Analysis, and Report Workflow Handoff

Generated: 2026-07-18 (Asia/Taipei)

This document is a continuation handoff for another Codex chat. It summarizes the current repository state, decisions already made, work completed, unfinished issues, and the proposed implementation order.

## Start here

Before changing anything, the next chat should:

1. Read the repository root AGENTS.md completely.
2. Read this handoff completely.
3. Run git status --short --branch and compare it with the baseline below.
4. Treat every pre-existing dirty file as user-owned until its origin is confirmed.
5. Do not stage, commit, push, merge, delete generated files, or rewrite history without explicit user authorization.
6. Teach changes at a junior full-stack level when explaining them: trace real files and requests, then implement one tested vertical slice at a time.

## Repository and Git baseline

- Workspace: F:/Cybercase Framework
- Current branch: codex/chat-analysis-report-workflow
- Previous branch name: codex/assignment-2026-07-17
- Current HEAD: b4c67b62c47edac60cdad9d0ae512e011192e9d9
- HEAD subject: Revert UI change
- HEAD also matches origin/revert-workflow-main and local revert-workflow-main.
- Local main: 1be0dfafe61e6fcefc5bd52a6ac7a5ae54aab6e7
- origin/main: 1be0dfafe61e6fcefc5bd52a6ac7a5ae54aab6e7
- Relative to main, the current branch is 1 commit ahead and 73 commits behind.
- The branch has no upstream and has not been pushed under its new name.
- There are no staged changes.

This is a rollback/compatibility branch. A direct pull request from this branch into current main would include a large historical rollback. If the final destination is main, the safer strategy is a new branch from current main followed by selective porting of the approved feature files.

## Original assignment

The attached thesis brief requested a minimal experimental LLM Analysis Module for:

Interactive Case Analysis and Report Generation Module

Its hypothesis is that an LLM-generated cyber-case analysis becomes more auditable when it is:

1. decomposed into atomic claims;
2. linked to preserved source passages;
3. checked with exact source spans;
4. checked deterministically for changed money, dates, IP addresses, hashes, and account identifiers;
5. classified by three-way semantic validation;
6. assigned an evidential status before report generation.

The brief explicitly required small, reversible, testable work and prohibited a production rewrite, new retriever, new vector database, new microservice, queues, model training, automatic legal conclusions, and unrelated refactoring.

The original brief also marked rag_service as read-only and said not to redesign the frontend. Later explicit user requests broadened those two boundaries:

- copy the updated main rag_service contents into this branch;
- redesign /chat as a three-section Codex-style workspace;
- add Chat, Evidence, MITRE Mapping, Timeline, and Report tabs;
- remove mock UI and mock data;
- ensure report generation is backend-owned rather than rag_service-owned.

The later explicit requests are why the current dirty tree contains synced rag_service files and a new frontend workspace. Do not confuse the copied upstream RAG changes with new analysis-module implementation.

## Current dirty working tree

Tracked changes:

- backend/app/config.py
- backend/app/main.py
- backend/app/routers/rag.py
- backend/app/schemas/rag.py
- frontend/src/app/chat/page.tsx
- frontend/src/components/FollowUpModule.tsx (deleted)
- frontend/src/lib/api.ts
- rag_service/app/RAG/GraphRAG/config.py
- rag_service/app/RAG/GraphRAG/pipeline/agent_graph.py
- rag_service/app/RAG/GraphRAG/retrieval/graph_retriever.py
- rag_service/app/RAG/GraphRAG/retrieval/reranker.py

Important untracked application files:

- backend/app/middleware/__init__.py
- backend/app/middleware/report_body_limit.py
- backend/app/routers/reports.py
- backend/app/schemas/case_analysis.py
- backend/app/services/case_analysis/__init__.py
- backend/app/services/case_analysis/service.py
- backend/app/services/reporting/__init__.py
- backend/app/services/reporting/generator.py
- backend/tests/test_case_analysis.py
- backend/tests/test_report_generation.py
- frontend/src/components/chat/ChatPanel.tsx
- frontend/src/components/chat/EvidencePanel.tsx
- frontend/src/components/chat/InspectorPanel.tsx
- frontend/src/components/chat/MitreMappingPanel.tsx
- frontend/src/components/chat/ReportPanel.tsx
- frontend/src/components/chat/TimelinePanel.tsx
- frontend/src/components/chat/WorkspaceSidebar.tsx
- frontend/src/components/chat/icons.tsx
- frontend/src/components/chat/types.ts
- rag_service/app/RAG/GraphRAG/docs/retrieval_perf_optimization.md
- rag_service/app/RAG/GraphRAG/docs/retrieval_perf_optimization_th.pdf

Other untracked areas include backend/evaluation, output, and tmp. The tmp tree is very large and contains generated thesis/PDF artifacts. Do not remove, stage, or report those generated artifacts as part of this implementation unless the user explicitly asks.

Never use git add -A on this branch. Use explicit file allowlists only.

## Work completed in this chat

### Branch and upstream synchronization

- Confirmed the original working branch was based on rollback commit b4c67b6.
- Checked origin/main.
- Fast-forwarded local main safely to origin/main at 1be0dfa.
- Copied tracked rag_service contents from updated main into the current branch without staging unrelated files.
- Verified all 107 tracked rag_service blobs matched local main after the copy.
- Renamed the branch to codex/chat-analysis-report-workflow.

### RAG validation already completed

The following passed after syncing the main RAG contents:

- python -m compileall -q rag_service/app
- python -m pytest -q rag_service/tests/test_stix_parser.py

Result: 5 tests passed with 2 warnings in 158.26 seconds.

The RAG health endpoint was also previously confirmed as HTTP 200 with rag_chain=true and rag_agent=true after reload.

These are historical results from this chat. Re-run relevant checks after any new edits.

### Database downgrade

The live PostgreSQL database was transactionally downgraded from revision 0007_mapping_review_gap to:

- 0001_initial_core_schema

Last confirmed retained tables:

- alembic_version
- cases
- users

Last confirmed row counts:

- cases: 8
- users: 0

Backup created before downgrade:

- C:/Users/kkham/AppData/Local/Temp/cybercase_pre_downgrade_0007_to_0001_20260718_003913.dump
- SHA256: A0D49D8ED6A7DE5ABB39E952E9F21EF647E88DB8C58BF219296C619C721B3792

After the downgrade, /api/v1/health and /api/v1/users/ previously returned HTTP 200.

Current refresh note: Docker Desktop was not running when this handoff was generated, so the database revision and service health could not be re-verified at handoff time.

### Frontend workspace

The dirty tree contains a new three-pane /chat workspace:

- left navigation/sidebar;
- center active workspace;
- right inspector panel;
- responsive inline inspector on narrower screens.

Tabs:

- Chat
- Evidence
- MITRE Mapping
- Timeline
- Report

The page uses real typed API data and no longer relies on the old mock FollowUpModule. The main orchestrator is frontend/src/app/chat/page.tsx.

### Backend analysis and report prototype

The dirty tree contains a typed experimental analysis flow:

- backend/app/schemas/case_analysis.py
- backend/app/services/case_analysis/service.py
- backend/app/services/reporting/generator.py
- backend/app/routers/rag.py

The backend endpoint is:

- POST /api/v1/rag/cases/{case_id}/experimental-analysis

It:

1. accepts a retrieval_context_id and case sources;
2. fetches one frozen RAG snapshot;
3. performs claim-level source and semantic validation;
4. assigns evidence statuses;
5. builds a CaseAnalysisArtifact;
6. deterministically generates a report only when the artifact is reportable.

The feature flag is disabled by default:

- EXPERIMENTAL_ANALYSIS_ENABLED=false

Set it to true for an enabled runtime smoke test.

## Current ownership boundaries

### Frontend owns

- presenting chat and follow-up questions;
- retaining the current browser-run state;
- presenting Evidence, MITRE, Timeline, Report, and inspector states;
- sending typed requests to backend /api/v1.

### Backend owns

- API boundary exposed to the browser;
- frozen-context validation;
- claim validation and evidence classification;
- reportability decisions;
- deterministic report generation.

### rag_service owns

- retrieval;
- GraphRAG follow-up sessions;
- query rewriting and re-retrieval;
- MITRE candidate construction;
- transient frozen retrieval-context cache.

rag_service currently exposes:

- GET /health
- POST /query
- POST /resume
- GET /retrieval-contexts/{context_id}

It does not expose a report-generation route. Keep report generation backend-owned.

backend/app/routers/reports.py exists as an untracked, unregistered router. backend/app/main.py intentionally does not register it. Existing tests require both legacy paths to remain absent:

- /api/v1/reports/generate
- /api/v1/rag/generate-report

Do not register the orphan router without a new explicit product decision.

## Current request flow

    Browser /chat
        -> POST backend /api/v1/rag/query
        -> backend proxies to rag_service /query
        -> GraphRAGAgent retrieves/evaluates
        -> completed response or follow-up session

    If follow-up:
        Browser
            -> POST backend /api/v1/rag/resume
            -> backend proxies to rag_service /resume
            -> GraphRAGAgent restores session and re-runs retrieval

    If completed:
        rag_service stores a frozen retrieval snapshot
            -> retrieval_context_id
        Browser calls backend experimental-analysis
        Backend fetches snapshot once
        Backend validates atomic claims
        Backend conditionally generates deterministic report
        Browser populates Evidence, MITRE, Timeline, and Report

The browser should call backend /api/v1 only. It should not call port 8001 directly.

## Important identifiers

- session_id: one-use continuation handle for a follow-up turn.
- retrieval_context_id: identifier for the frozen RAG context, answer, raw result, and MITRE rows.
- case_id: current analysis identity; the /chat prototype generates it in the browser.

The retrieval cache is in RAG process memory, uses a sliding one-hour TTL, and is lost when rag_service restarts.

## Primary unfinished bug: resumed-query provenance

The copied upstream agent graph now correctly supports multiple consecutive follow-ups. It preserves:

- original_query;
- rewritten_queries;
- incident_facts;
- asked_slots.

However, rag_service/app/routers/rag.py currently stores a completed resumed snapshot with:

    query=request.answer

That is incorrect. The actual retrieval used the original case query plus accumulated rewrites, but the snapshot is labeled with only the latest short answer.

The backend validator in backend/app/services/case_analysis/service.py requires the submitted case description to match, or be a long substring of, snapshot.query. Therefore a legitimate follow-up completion normally fails retrieval-context binding.

The frontend currently acknowledges this limitation and does not invoke validated analysis after a completed follow-up. It displays:

    Validated analysis is unavailable for this follow-up run.

This is a cross-service contract bug, not merely a missing frontend call.

## Proposed next implementation sequence

No implementation of the following sequence has started. The user requested a plan and junior-level teaching, but did not yet authorize proceeding with code changes.

### 1. Protect the baseline

- Re-record Git status and unstaged diff.
- Preserve all unrelated and generated files.
- Use explicit edit/stage allowlists.

### 2. Fix RAG provenance

Smallest proposed contract repair:

1. Add original_query to the internal AgentResponse dataclass.
2. Populate it from graph state for completed and follow-up responses.
3. In rag_service /resume, store response.original_query rather than request.answer.
4. Fail closed if a completed resumed response has no original query.
5. Do not add a report route to rag_service.

Focused tests should use fakes and must not load BGE-M3, Neo4j, or a paid LLM:

- completed resume stores the original case query;
- first resume may return another follow-up with a fresh session ID;
- final resume produces a context ID;
- final snapshot query remains the original case;
- no usable snapshot is claimed before retrieval completes.

### 3. Complete backend integration

- Keep the existing retrieval-context binding check.
- Confirm initial and resumed snapshots behave identically after the RAG repair.
- Preserve the original frozen MITRE table.
- Keep retrieved MITRE knowledge review-only; it cannot prove incident occurrence.
- Test 404 expired context, 502 malformed/upstream context, 504 timeout, feature flag disabled/enabled, and OpenAPI route ownership.
- Ensure deterministic report generation makes no HTTP or LLM call.

### 4. Complete frontend follow-up analysis

In frontend/src/app/chat/page.tsx:

- retain originalCaseDescription;
- retain pendingFollowUpQuestion;
- retain structured followUpAnswers;
- append each question/answer pair with a stable source ID;
- after the final completed resume, invoke analyzeCase with the original description, final retrieval_context_id, and accumulated follow-up answers;
- share one analysis helper between direct completion and follow-up completion;
- preserve runTokenRef stale-response protection;
- reset all derived state during New analysis;
- remove FOLLOW_UP_ANALYSIS_LIMITATION only after the cross-layer flow is proven.

### 5. Complete real tab behavior

- Evidence should display validated claims and source passages.
- MITRE Mapping should display frozen RAG candidates and clearly mark them as candidates/review-only.
- Report should display only the backend-generated deterministic report or explicit reportability reasons.
- Timeline must remain honestly empty until the backend emits validated events.

Timeline is not currently just a UI gap:

- Case analysis intentionally returns timeline_events=[].
- The report admission gate currently rejects non-empty auxiliary timeline data.

A later Timeline slice must derive events only from accepted, cited case claims and update report admission to validate those events rather than trusting raw LLM auxiliary text.

### 6. Repair Alembic source compatibility

Current checkout facts:

- backend/alembic.ini exists and is tracked.
- backend/alembic/env.py is missing.
- backend/alembic/versions contains only .gitkeep.
- backend/requirements.txt lacks Alembic and pytest.
- backend/app/config.py exposes settings.async_database_url.
- backend/app/database.py currently ignores it and manually uses POSTGRES_* connect_args.

Restore only the minimum 0001 toolchain from current main:

- backend/alembic/env.py
- backend/alembic/versions/0001_initial_core_schema.py
- Alembic and pytest requirements
- one shared async database URL for application and migrations

Do not restore migrations 0002 through 0005 on this compatibility branch unless the user explicitly requests their schema.

Test migration downgrade/upgrade only against a disposable database. Inspect the user database with alembic current; do not round-trip it for a regression test.

### 7. Validate the whole vertical slice

Suggested order:

    git diff --check
    python -m compileall -q rag_service/app
    python -m pytest -q rag_service/tests/test_rag_resume_context.py
    python -m pytest -q rag_service/tests/test_stix_parser.py
    python -m pytest -q backend/tests
    npm --prefix frontend run lint
    npm --prefix frontend exec tsc -- --noEmit --incremental false
    npm --prefix frontend run build
    doppler run -- docker compose config --quiet
    doppler run -- docker compose build backend rag-service frontend
    doppler run -- docker compose up -d

Runtime smoke:

1. backend health;
2. RAG health after model startup;
3. initial query completion;
4. chained follow-up;
5. final resumed context snapshot;
6. backend validated analysis;
7. Evidence/MITRE/Timeline/Report UI;
8. report route absence in rag_service;
9. backend and RAG logs with timestamps;
10. database migration revision.

Initial RAG readiness can lag while models load. A successful image build is not proof that the full workflow works.

### 8. Final review and packaging

- Compare final Git status with the baseline in this document.
- Inspect the complete unstaged and staged diff.
- Keep output, tmp, caches, generated PDFs, and unrelated evaluation artifacts out of commits.
- Use logical commits only after explicit authorization.
- Do not push or open a pull request unless asked.

Potential commit boundaries:

1. RAG resumed-query provenance and tests.
2. Backend analysis/report integration and tests.
3. Frontend follow-up lifecycle and workspace.
4. Alembic 0001 tooling repair.

## Existing test coverage worth preserving

backend/tests/test_case_analysis.py covers:

- accepted reported claims;
- amount/date/IP/hash/account mismatch checks;
- semantic contradiction and insufficient-information behavior;
- fabricated or ambiguous quotations;
- retrieved MITRE knowledge remaining review-only;
- context ID and query binding;
- frozen-context fetch behavior and timeout/error mapping;
- feature flag behavior.

backend/tests/test_report_generation.py covers:

- deterministic report generation;
- forged claim prose exclusion;
- non-reportable artifacts;
- size/body limits;
- hidden legacy report paths;
- no HTTP or LLM use during report generation.

Missing focused coverage:

- real multi-turn GraphRAG resume contract;
- resumed snapshot preserving original query;
- frontend automated tests;
- batch graph retrieval equivalence;
- CPU/CUDA device-selection behavior;
- self-contained Alembic 0001 migration smoke.

## Known limitations and risks

- The current branch is substantially behind main.
- The working tree mixes several scopes and contains many generated artifacts.
- The new application files are not staged or committed.
- Experimental analysis is disabled by default.
- Frozen contexts are transient and disappear on RAG restart.
- Browser-generated case IDs are not database ownership proof.
- Caller-supplied case and evidence text is not bound to a persisted case version.
- A direct text match proves snapshot/query consistency, not chain of custody.
- Timeline data is intentionally empty until it can be evidence-bound.
- Docker Desktop was unavailable when this handoff was written.
- No new provenance fix described above has been implemented yet.

## Recommended first prompt in the next chat

Use:

    Read F:/Cybercase Framework/AGENTS.md and
    F:/Cybercase Framework/CODEX_HANDOFF_CHAT_ANALYSIS_REPORT_WORKFLOW.md.
    Verify the current Git baseline without modifying files. Then continue
    Lesson 1 at junior-developer level and implement only the resumed-query
    provenance fix with focused tests. Preserve every unrelated dirty change.

If the next chat is for teaching only, replace implement with explain and do not modify files.
