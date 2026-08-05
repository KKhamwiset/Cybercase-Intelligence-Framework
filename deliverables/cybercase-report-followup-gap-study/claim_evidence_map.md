# Claim-Evidence Map

Status vocabulary: **supported** means directly evidenced by current code or verified primary sources; **proposed** requires the preregistered future work; **unsupported** must not be claimed from this package.

## Current and literature claims

| Claim | Existing evidence | Required future evidence | Metric/check | Status |
|---|---|---|---|---|
| Dehing uses two-stage per-part extraction then synthesis with exact Trace IDs. | [Publication record](https://research.rug.nl/en/publications/structured-report-generation-using-local-llms-for-chat-based-digi/) and [official repository](https://github.com/NetherlandsForensicInstitute/local-llm-chat-report-benchmark). | None for method description. | Prompt/runner inspection. | supported |
| Crystal Clear is one fictitious chat case split into ten approximately-29k-token parts, one 29,864 due to boundary preservation. | Frozen NFI repository commit and split artifacts. | Recheck hashes at acquisition. | Part count/token metadata. | supported source fact |
| Dehing's strict citation and chronology remain weak and reports are provisional triage. | Publication abstract/conclusion. | None for scoped literature statement. | Citation support audit. | supported |
| FollowupQ uses specialist-agent pools/filtering and RIM does not penalize extra questions. | [ACL paper](https://aclanthology.org/2025.acl-long.1226/) Sections 3–5. | None for scoped literature statement. | Paper-method audit. | supported |
| Current backend exposes health/chat and calls RAG only through `/query`. | `backend/app/main.py:28-37`; `backend/app/services/chat/rag_client.py:24-37`. | Re-audit if checkout changes. | Route/call-site inventory. | supported current snapshot |
| Current report UI is deterministic client-side demo output, non-persistent and unverified. | `frontend/src/components/chat/ChatReportView.tsx:26-44,63-81`; `frontend/src/lib/chat-demo-report.ts:142-150`. | None for dirty snapshot; re-audit later revisions. | Code-path inspection. | supported current snapshot |
| Current retrieval context is not durable lineage. | In-memory dictionary and one-hour TTL in `rag_service/app/routers/context_store.py:10-18,33-68`. | Persistence tests if redesigned. | Restart/expiry/source-ID contract. | supported current snapshot |
| Current policy prompt requests one fact, but runtime validation does not prove semantic atomicity. | Prompt `backend/app/services/chat/followup_policy.py:15-31`; validator `:50-65`. | Runtime output annotation. | Compound-question rate. | supported current snapshot |
| Current M365 preprompt is a dirty, untracked generality contaminant. | `analysis_prompt.py:6-22`; blob hash recorded in `project_inventory.md`. | Remove/isolate before general experiment. | Snapshot/hash audit. | supported dirty snapshot |
| Current follow-up pilot establishes workflow feasibility only. | `experiments/followup_pilot/README.md:96-104` and evaluator limitations. | Multi-case preregistered runs. | None beyond observed workflow. | supported narrow claim |

## Proposed research claims

| Proposed paper claim | Existing evidence | Required future evidence | Metric/check | Status |
|---|---|---|---|---|
| B0-reproduction preserves the exact NFI prompts/schema and adds no ATT&CK output. | Protocol and upstream snapshot only. | Released-artifact recomputation, parity checklist, one fresh primary-model run, hashes. | Prompt/schema/hash parity; Trace-ID scores. | proposed |
| B0-external-adapted is a declared adaptation, not a faithful reproduction. | Adaptation list in `evaluation_protocol.md` and `research_gap.md`. | Final implementation diff/manifests. | Adaptation checklist. | proposed design boundary |
| B1 differs from B0-external-adapted only by one gate and eligible canonical answer. | Package contracts only. | Run-manifest equality for source/model/prompts/schema/decoding plus treatment audit. | Treatment-isolation check. | proposed |
| B1 asks only for eligible report-critical gaps. | No outcome evidence. | Gold case kinds, gate logs, blinded labels. | Necessity precision/recall; unnecessary-question rates. | proposed |
| B1 targets the correct slot and resolves eligible gaps. | No outcome evidence. | Canonical answer IDs, target slots, resolution logs. | Target-slot accuracy; resolved-gap rate; burden. | proposed |
| B1 improves supported claims relative to B0-eligible-masked. | No experiment run. | Matched intention-to-treat outputs across frozen external cases. | Primary supported-claim F1 difference; recovery where denominator > 0. | proposed |
| B1 improves exact ATT&CK mapping. | No experiment run. | Frozen ATT&CK gold and matched outputs. | Micro/macro F1; exact-set accuracy; over-mapping. | proposed secondary |
| B1's harm deltas on sufficient and explicitly-unknown cases can be estimated descriptively. | No experiment run. | Matched gate-off/on controls with all seven family effects. | Question rate; supported-claim F1 delta; ATT&CK false-positive delta; mean/median family effect. | proposed descriptive analysis; no equivalence or safety claim |
| Evidence lineage enables auditing. | Schema and validator encode resolvable references. | Validator use and human support judgments. | Reference validity and lineage completeness. | supported as artifact capability; outcome unmeasured |

## Claims that remain unsupported

| Claim | Why unsupported | Evidence needed | Status |
|---|---|---|---|
| B0-external-adapted faithfully reproduces Dehing. | Source, schema, prompts, reference, and metrics are adapted. | Not repairable by wording; keep strata separate. | unsupported / do not claim |
| Current CyberCase is B0 or already implements research B1. | No upstream two-stage report path or between-stage report-schema gate exists. | Separate implementation and validation. | unsupported |
| B1 improves real-world forensic accuracy, trust, or response. | Synthetic sources and no field deployment. | Multi-site realistic validation. | unsupported |
| B1 reduces analyst effort. | No user study. | Counterbalanced analyst study. | unsupported |
| Evidence lineage guarantees truth. | A valid link can still support a wrong inference or contain wrong source data. | Substantive claim adjudication. | unsupported |
| Novelty follows from RAG, agents, HITL, ATT&CK, follow-up, or provenance. | These ingredients pre-exist. | Novelty rests on the narrow treatment/evaluation result. | unsupported |

## Required external evidence chain

For every eligible affected claim:

`withheld source span -> target_slot_id -> one question -> canonical answer_id -> resolution status -> answer/source lineage -> final claim and ATT&CK decision`

For controls, the chain stops at a schema-valid proceed decision: there is no question and no controlled answer. Unaffected claims use per-variant `retain_supported` expectations. The semantic validator checks references and leakage; blinded annotators still decide substantive support.
