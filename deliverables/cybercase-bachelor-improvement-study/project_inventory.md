# Project Inventory

## Snapshot warning

Inspected on 2026-08-05 at Git HEAD `0011d89c35b8906a9bb01defe5d55c2e54bb97c1`. The working tree was already dirty in backend, RAG-service, experiment-result, and deliverable paths. This is a live-snapshot inventory, not a clean-commit audit. Current application and pilot outputs are excluded as research evidence.

## Repository map

| Area | Current role | Research consequence |
|---|---|---|
| `backend/app/routers/chat.py`, `backend/app/models/chat.py`, `backend/app/services/chat/` | Plain-text chat threads, messages, runs, and clarification orchestration | Persists chats, not case files, exhibits, evidence, or research reports. |
| `backend/app/services/chat/chat_worker.py` | Resolves follow-up before calling RAG and builds one clarified query string | Not B0 or B1; its product policy cannot be treated as the scientific control. |
| `backend/app/services/chat/rag_client.py`, `backend/app/schemas/chat/rag.py` | Sends `POST /query` with one `query: str` | No frozen multi-artifact packet or evidence-citation contract crosses this boundary. |
| `rag_service/app/routers/context_store.py` | In-memory, TTL retrieval-context cache | Provenance/context is transient, not a persisted case-file record. |
| `frontend/src/components/chat/ChatReportView.tsx`, `frontend/src/lib/chat-demo-report.ts` | Client-side, non-persistent, explicitly unverified demo report | Not a research report generator and not evaluation evidence. |
| `experiments/followup_pilot/` | Existing product-oriented follow-up pilot artifacts | Different unit and treatment; exclude from the proposed experiment. |
| `deliverables/cybercase-bachelor-improvement-study/` | Planning and story package | Defines the future isolated study; contains no outcomes. |

The dirty `backend/app/services/chat/analysis_prompt.py` also contains a Microsoft 365-specific prompt. That case-specific bias is another reason not to route arbitrary research dossiers through the current product path.

## Method evidence

No current module implements Dehing-style case-file Stage 1/Stage 2 reporting with persistent `evidence_id` and `source_locator` references. No current module implements the approved three-perspective, hidden-gold, target-matched B1. The implementation must therefore be isolated under `experiments/` and must reuse neither product output nor pilot scores as proof.

## Experiment evidence

There are no frozen CFReDS/CASE packets, preregistered gaps, B0/B1 run logs, raw reports, scorer sheets, agreement records, or result tables for this study. Existing `experiments/followup_pilot/results/` files test a different product flow and do not answer the proposed RQs.

## Writing assets

- `README.md`: concise decision and package map.
- `bachelor_research_plan.md`: thesis scope, conditions, RQs, and execution plan.
- `dataset_and_experiment_plan.md`: source, packet, masking, metrics, and analysis contract.
- `paper_story.md`: complete focused-paper story and claim boundary.
- `dataset_source_manifest.json`: access, role, reuse, and redistribution record.
- `references.bib`: method, dataset, reuse, and motivation sources.

No manuscript template, figures, tables, or completed thesis/paper draft is present in this package.

## Citation assets

`references.bib` contains Dehing, FollowupQ, CFReDS Data Leakage, NIST reuse guidance, CASE Owl, Digital Corpora terms, EvidenceForge, Thai Police Open Data, and NFI method-provenance records. Citation metadata and sentence-level support still require final manuscript verification.

## Missing inputs

- exact downloaded source versions, file list, hashes, and artifact-level reuse review;
- frozen packet schema/instances and deterministic packet-builder code;
- eight preregistered gaps, acceptable targets, hidden answers, and gold evidence locations;
- fixed prompts, report schema, model/provider versions, seeds/decoding, and repeat policy;
- executable B0/B1 harness under `experiments/`;
- raw outputs, latency/token/call logs, double-scoring sheets, agreement/adjudication logs, and descriptive result tables;
- examiner review and, if attempted, human-verified Thai translation records.
