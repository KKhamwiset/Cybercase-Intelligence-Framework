# Worktree and Markdown Status

Snapshot date: 2026-08-13. This note is a diagnostic snapshot, not a promise
that the worktree is clean.

## Markdown files

The tracked Markdown status observed at snapshot time:

- `README.md` is modified (`M`). Its current diff removes the deleted demo
  extraction file from the service tree. Preserve this user change.
- The experiment output
  `experiments/report_architecture_b0_b1_b2/outputs/20260807T145601Z_2f1a3210/repeatability_summary.md`
  is untracked.
- No repository `.codex` or `knowledge` directory existed before this note.
- Existing architecture/integration documents under `docs/` and
  `rag_service/docs/` are historical/current mixed documentation. Check source
  and tests before relying on endpoint or pipeline claims.
- There is a known route-documentation conflict: `backend/app/routers/chat.py`
  currently implements chat-scoped report endpoints (and the route-surface
  tests cover them), while `AGENTS.md`,
  `backend/README.md`, and parts of the older integration notes describe the
  report view as client-only/no backend report lifecycle. The standalone
  top-level `/api/v1/reports` route remains absent. Treat the live router and
  tests as the current implementation until the product/documentation conflict
  is explicitly resolved.

## Broader dirty worktree

The worktree also contains active changes in backend models, migrations,
schemas, chat orchestration, extraction, frontend chat components, RAG
pipeline/router code, tests, and experiment directories. These changes belong
to the ongoing workspace and must not be reset or silently folded into a docs
cleanup.

## Safe documentation workflow

1. Read this index and the relevant source-backed note.
2. Verify behavior in code/tests before editing an existing document.
3. Add new knowledge notes under `docs/codex-knowledge/` when the change is
   architectural or cross-service.
4. Keep generated/runtime logs, secrets, raw incident text, and provider output
   out of committed Markdown.
5. Before handoff, run `git diff --check` and report the exact Markdown paths
   changed; do not claim the whole repository is clean.
