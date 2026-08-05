# Bachelor Research Plan

## Working title

**Does One Bounded Clarification Improve Evidence-Grounded Cyber-Investigative Case-File Drafts?**

## Aim and contribution boundary

The study asks whether one targeted clarification before report drafting changes the evidence-grounded quality of a provisional report produced from an incomplete cyber-investigative case file (สำนวนคดี). It integrates reduced adaptations of two published ideas; it does not propose a new question-generation or reporting mechanism.

One experiment supports two deliverables:

- the **Bachelor thesis** documents the case-file representation, source preparation, isolated implementation, full scoring protocol, results, and limitations;
- the **research paper** reports the focused B0/B1 empirical comparison, question-target behavior, and added cost.

## Scientific unit and output

Each input is a frozen, multi-artifact packet containing a mandate/scenario, evidence register, acquisition and integrity records, and text or structured evidence exhibits. Each item has a stable `evidence_id`, a dataset-neutral `source_locator`, and provenance. The output is a **provisional investigative report draft**. It is never presented as a final forensic conclusion and must be checked by a qualified examiner against the source artifacts.

## Conditions

### B0: published reporting baseline adapted to a case file

1. Stage 1 extracts report-relevant findings from the frozen packet and retains `evidence_id` plus `source_locator` for every finding.
2. Stage 2 synthesizes the ordered extraction into the fixed report schema without changing evidence identity or inventing support.

This is Dehing-style two-stage extraction/synthesis with dataset-neutral citations, not a claim that Dehing evaluated case-file dossiers.

### B1: one reduced clarification, then unchanged B0

1. Before B0, three fixed perspectives propose questions: **entity/role**, **chronology**, and **evidence/citation**.
2. A bounded filter removes answered, redundant, vague, or unanswerable candidates and selects at most one question using only the visible incomplete packet.
3. Only after selection, the evaluation harness compares the question with the preregistered acceptable target set. Hidden findings, answers, and gold citations are never exposed during generation or filtering.
4. On a match, the harness adds a separate `supplemental_investigator_statement` with its own statement ID, source type, provider, target-gap ID, and provenance. On a mismatch, no statement is added.
5. The exact B0 from above then runs without prompt, schema, model, or decoding changes.

This is a reduced FollowupQ-inspired adaptation, not a faithful reproduction of FollowupQ.

## Research questions

- **RQ1:** What evidence-grounded report quality does B0 achieve on preregistered incomplete case-file conditions?
- **RQ2:** What paired change in report quality occurs when the single B1 clarification precedes the same B0?
- **RQ3:** How often does B1's selected question match the target gap, and what redundancy, answerability, latency, token, and model-call cost does it add?

## Feasible execution plan

1. Freeze source versions and reuse records described in [dataset_and_experiment_plan.md](dataset_and_experiment_plan.md).
2. Prepare six CFReDS Data Leakage missing-finding conditions and two CASE Owl transfer gaps. Preregister the required findings, acceptable question targets, answer text, and source provenance before viewing model output.
3. Implement the research harness under `experiments/`; do not make product backend, frontend, or RAG outputs part of the experiment.
4. Hold the packet, B0 prompts/schema, model, decoding, and scoring rules fixed within each paired comparison. Use three repeats if inference is stochastic; otherwise record the settings and evidence for deterministic execution.
5. Score required-finding recall, claim support, evidence references, entity/timeline correctness, question behavior, and cost. Aggregate gaps within each case and report descriptive paired differences only.
6. If feasible, independently double-score all paper-primary outputs; report agreement and an adjudication log. Any reduced double-scoring scope must be declared before results are examined.

## Claims and limits

If supported, the thesis and paper may report measured paired differences for these frozen English-source cases and the cost of one clarification. They must not claim novelty, statistical significance, operational readiness, general cyber effectiveness, native Thai effectiveness, or examiner replacement. A supplemental statement is investigator-provided information, not forensic proof. It is scored separately as investigator-reported and receives forensic evidence-support credit only if it introduces a separately registered exhibit with a resolvable source locator.
