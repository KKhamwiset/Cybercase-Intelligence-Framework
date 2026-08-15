# Codex Knowledge Index

This directory is a compact, source-backed orientation layer for Codex work in
the CyberCase repository. It describes the current checkout as observed on
2026-08-13; it is not a replacement for the implementation or its tests.

When a document here conflicts with code, schemas, migrations, or tests, treat
the executable source as authoritative and update the relevant knowledge note.

## Current snapshot

- Branch: `main`
- Baseline commit observed: `7522fa0db622e9c502ec27c153b80852e816713e`
- Alembic chain currently includes `0005_rag_contexts`.
- The worktree is intentionally dirty with user/feature changes across
  backend, frontend, RAG, migrations, tests, and experiments.
- `README.md` is modified and should not be overwritten by automated cleanup.

## Notes

- [01-current-architecture.md](01-current-architecture.md) — service boundaries
  and the current initial-analysis / ASK lifecycle.
- [02-chat-analysis-contract.md](02-chat-analysis-contract.md) — Case State,
  Main Case Analysis, durable context, and post-answer action rules.
- [03-rag-backend-contract.md](03-rag-backend-contract.md) — RAG pipeline,
  HTTP boundary, retrieval snapshot, MITRE table, and answer isolation.
- [04-worktree-and-doc-status.md](04-worktree-and-doc-status.md) — Markdown
  status and the known documentation drift to check before editing docs.

## Update rule

Keep these notes short and factual. Include source paths when documenting a
behavior, and record a date when documenting a volatile runtime or worktree
state. Do not copy secrets, provider responses, incident content, or database
data into this directory.
