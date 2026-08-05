# Project Inventory

Audit date: 2026-08-04. This inventory describes a **dirty working-tree snapshot**, not a commit and not experimental evidence.

## Reconstructable snapshot identifiers

| Item | State | Identifier | Use in this inventory |
|---|---|---|---|
| Repository HEAD | committed base | `0011d89c35b8906a9bb01defe5d55c2e54bb97c1` | Base for every tracked line anchor. |
| `backend/app/services/chat/chat_worker.py` | modified tracked | stable patch ID `5aa33c79cfb91eef6dbc5940dd1a910dc7d63ab0` | Supports the audited pre-RAG policy/order claim. Recompute with `git diff -- backend/app/services/chat/chat_worker.py | git patch-id --stable`. |
| `backend/app/services/chat/analysis_prompt.py` | untracked | Git blob hash `05fbe33eb33d69a58b1aa4afc18d1b6725f71bb3` | Supports the M365-specific prompt/generalization warning. |

Other dirty application/test/Docker files existed at audit time but are not evidence for the claims below, so their hashes are intentionally not promoted into this research snapshot. To reproduce a code claim, check out the HEAD above, apply the exact worker patch whose stable patch ID matches, restore the untracked prompt blob, and then verify the cited content. A patch ID is an integrity identifier, not a substitute for preserving the patch itself.

## Current code-path truth

| Boundary | Exact repository evidence | What it establishes | Status |
|---|---|---|---|
| Backend routes | `backend/app/main.py:28-37` | Registers only health and chat routers under `/api/v1`; no backend report route. | Tracked at HEAD |
| RAG client | `backend/app/services/chat/rag_client.py:24-37` | Calls only the RAG service `/query` completed-response boundary. | Tracked at HEAD |
| Policy instruction | `backend/app/services/chat/followup_policy.py:15-31` | Prompt asks for exactly one concise question about one fact and forbids asking for ATT&CK IDs/general knowledge. | Tracked at HEAD |
| Policy syntax validation | `backend/app/services/chat/followup_policy.py:50-65` | Rejects empty, over-length, multiline, or more-than-one-question-mark output. It does **not** semantically detect a compound single-mark question. | Tracked at HEAD |
| Round budget | `backend/app/config.py:85-92`; `backend/app/services/chat/chat_worker.py:352-405` | Production policy may continue for up to three rounds and persists an awaiting-followup outcome. This is not the research one-question budget. | Config at HEAD; worker at identified dirty patch |
| Ordering | `backend/app/services/chat/chat_worker.py:483-512` | Dirty snapshot adds the analysis preprompt, runs follow-up policy before RAG, combines prior clarification, then calls RAG. There is no Dehing Stage 1 report artifact or report-schema gate. | Identified dirty patch |
| M365 contamination | `backend/app/services/chat/analysis_prompt.py:6-22` | Untracked prompt hardcodes Microsoft 365 initial access/sub-technique, so the dirty runtime is not domain-general. | Identified untracked blob |
| Demo extraction | `backend/app/services/chat/demo_extraction.py:42-93` | Generates `E-###`/`T-###` candidate IDs from chat segments; these are not immutable source record IDs. | Tracked at HEAD |
| RAG retrieval context | `rag_service/app/routers/context_store.py:10-18,33-68` | Stores context in process memory with a one-hour sliding TTL. It is not durable experimental lineage. | Tracked at HEAD |
| RAG behavior | `rag_service/app/RAG/GraphRAG/pipeline/agent_graph.py:1-28,387-402,756-786`; `pipeline/evaluator.py:188-230,305-369` | RAG autonomously broadens and returns a completed answer; it does not pause for user clarification and can fail open/force sufficient. | Tracked at HEAD |
| Client report builder | `frontend/src/lib/chat-demo-report.ts:32-44,142-150` | Builds an explicitly unverified, non-persistent chat-text report locally. | Tracked at HEAD |
| Report UI | `frontend/src/components/chat/ChatReportView.tsx:26-44,63-81` | React state invokes the local builder; label says demo/unverified. | Tracked at HEAD |
| Pilot evaluator | `experiments/followup_pilot/evaluator.py:55-95,115-182`; `schemas.py:30-69` | Scores fixed M365 fields and pairwise outputs; recovery uses a fixed two-field denominator and the scorer sees both outputs/reference checklist. | Tracked at HEAD |
| Pilot limitations | `experiments/followup_pilot/README.md:96-104` | One synthetic case, judgment error, and extra-call confounding are acknowledged. | Tracked at HEAD |

## Scientific boundaries

### B0-reproduction is absent

No repository path executes the frozen NFI Crystal Clear Stage 1/Stage 2 prompts and upstream report schema. The official [publication](https://doi.org/10.1145/3785318.3785330) and [repository](https://github.com/NetherlandsForensicInstitute/local-llm-chat-report-benchmark) remain the fidelity source. Current CyberCase is an implementation vehicle, not B0.

### B0-external-adapted and B1 are proposed

The current product does not implement the fixed CAM-LDS-compatible external report/ATT&CK schema, three-kind case contract, between-stage one-question gate, canonical answer, or matched eight-row experiment. Those are defined only in this deliverable package.

### Demo IDs and retrieval IDs are not evidence lineage

Demo IDs enumerate generated candidates rather than original logs/records. `retrieval_context_id` names a transient cache entry. Neither supplies dataset version/hash, immutable source span, mask, answer ID/provenance, target slot, claim link, or ATT&CK decision required by the external study.

## Evaluator limitations that the new protocol corrects

- Direct two-output presentation can create comparison anchoring; new report scoring uses separately randomized opaque outputs.
- Hidden-field recovery currently counts annotated requested fields rather than verifying semantic necessity, target slot, canonical answer resolution, or downstream lineage.
- The fixed two-hidden-field denominator is not a masked-to-complete recovery denominator.
- `correct_supported` is a manual label without the frozen exact/equivalence matching and one-to-one claim rules now specified.
- Pairwise shuffling hides method names only; it does not provide family-grouped inference or matched gate-off controls.

## Artifact status

The schema, three fictitious examples, semantic validator, run matrix, and documents in this package are implemented planning artifacts. No NFI reproduction, external model run, B1 outcome, or statistical result is present. Historical results under `experiments/followup_pilot/**` remain feasibility observations and are not absorbed into this study.
