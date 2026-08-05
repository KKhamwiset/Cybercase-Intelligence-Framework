# Preregistration-Ready Evaluation Protocol

Status: prospective protocol. No model run or effectiveness result is reported. Freeze this document, prompts, schemas, cases, and exclusions before test outcomes are inspected.

## Two strata, one treatment

### B0-reproduction: fidelity stratum

**B0-reproduction** uses the frozen [NFI Crystal Clear benchmark](https://github.com/NetherlandsForensicInstitute/local-llm-chat-report-benchmark) at commit 5554ef79a0bce3342fb827da2511366ea71b7390. It retains the released Stage 1 and Stage 2 prompts, report schema, Trace-ID convention, split logic, and evaluation artifacts. The corpus has ten approximately-29k-token parts; one part is 29,864 tokens because the splitter preserves a boundary. No ATT&CK field or clarification gate is added.

Recompute released validation/scoring artifacts for all five published local-model outputs. Require one fresh two-stage run with one predeclared hardware-feasible primary model. Choose it before new outcomes using hardware/memory fit, context-window fit, licensing, and ability to reproduce the released serving/quantization configuration. Fresh runs of the other four models are optional robustness checks. The Gemini report remains a generated reference requiring deterministic Trace-ID and human scrutiny.

### B0-external-adapted and B1: causal stratum

**B0-external-adapted** applies the two-stage extraction-then-synthesis pattern to fixed CAM-LDS-compatible case inputs and a fixed report-plus-ATT&CK schema, with no clarification gate. **B1** is exactly B0-external-adapted plus one schema-gated report-critical clarification opportunity between Stage 1 and Stage 2. Evidence lineage is fixed measurement infrastructure in every external arm, not a treatment.

Adaptations from the published B0 are declared rather than described as faithful reproduction:

1. The source changes from one fictitious multi-device chat corpus to versioned cyber evidence/timeline cases, primarily CAM-LDS v2.
2. Upstream Trace IDs and chat-part inputs become immutable source spans with offsets, case kinds, and grouped external splits.
3. The upstream report schema becomes one frozen external schema containing report claims, timeline events, and exact ATT&CK decisions.
4. The generated Gemini reference becomes human-adjudicated claim, timeline, ATT&CK, gap, and gate gold.
5. Prompts are adapted only as needed for the external input and output contracts; prompt hashes are frozen and published.
6. External metrics add gate necessity, target-slot resolution, answer uptake, evidence lineage, and ATT&CK accuracy.

Therefore B0-reproduction tests fidelity only. It is not pooled into, used as the counterfactual for, or described as part of the external B1 causal effect.

## Research questions and hypotheses

| ID | Question | Preregistered status |
|---|---|---|
| RQ1 | Can the released NFI B0 artifacts be recomputed and one primary-model run be reproduced under a recorded environment? | Fidelity is assessed by prompt/schema/hash parity, output structure, and recomputed Trace-ID scores; numerical equivalence is not presumed. |
| RQ2 | Does B1 ask one necessary, answerable question for an eligible gap and proceed on sufficient or explicitly-unknown controls? | **H1:** B1 has high eligible-case necessity and target-slot accuracy while gate-on controls have low unnecessary-question rates. |
| RQ3 | Does one resolved clarification improve the adapted external report? | **H2:** B1-eligible-clarified improves paired supported-claim F1 over B0-eligible-masked; exact ATT&CK mapping accuracy is secondary. |
| RQ4 | What downstream and burden changes appear when the gate is enabled on cases that need no answer? | **H3 (descriptive objective only):** estimate paired B1-minus-B0 harm deltas on sufficient and explicitly-unknown cases and report all seven family effects. No near-zero threshold, equivalence margin, safety hypothesis, or equivalence test is specified. |

H1 and H2 are untested confirmatory directional hypotheses. H3 is retained only as a descriptive label, not a confirmatory hypothesis. No hypothesis treats evidence lineage, additional agents, or the NFI reproduction as a second intervention.

## Units, grouping, and leakage boundary

- The external unit is one schema-valid case. The case kind is eligible_masked, sufficient, or explicitly_unknown.
- For CAM-LDS, inference_group is the seven-family scenario family. Multiple simulation runs, derived cases, or eligible gaps within one family are averaged before inference.
- split_group is also assigned at scenario-family level so a family cannot cross development/test. The validator rejects inconsistent cross-file assignments.
- Every condition derived from one case shares the same case, source, model build, decoding, Stage 1/2 prompts, repetition seed, and scoring procedure.
- Freeze MITRE ATT&CK STIX commit a6c366439edee3a87b79cf90dc0b93f5d7975956. Score exact technique/sub-technique IDs; parent credit is descriptive only.
- The complete variant, withheld spans, canonical answer, gold question, gold claims, and gold ATT&CK labels are sealed from B0-eligible-masked and from B1 at gate-decision time.

## Eight-row run design

The authoritative machine-readable grid is [run_matrix.csv](run_matrix.csv).

| Run | Purpose | Matched comparison |
|---|---|---|
| b0_reproduction_crystal_clear | Exact upstream fidelity; no added ATT&CK output | RQ1 only; no external causal comparison |
| b0_complete | Attainable reference for eligible external cases | Recovery denominator only |
| b0_eligible_masked | Gate-off incomplete comparator | Primary H2 comparator |
| b1_eligible_clarified | Only treatment: gate, one canonical answer, then identical synthesis | H1 and H2 |
| b0_sufficient / b1_sufficient | Matched gate-off/on sufficient inputs | H1 specificity and H3 descriptive harm |
| b0_explicitly_unknown / b1_explicitly_unknown | Matched gate-off/on explicit-unavailability inputs | H1 redundant-question control and H3 descriptive harm |

Gate-on negative controls must proceed without a question. A second question is a hard protocol failure. The primary causal comparison remains b1_eligible_clarified minus b0_eligible_masked.

## Execution controls and budgets

1. Freeze dataset files/hashes, case JSON, schema, validator, split assignments, prompt hashes, primary model/artifact hash, serving software, quantization, context limits, decoding, hardware, dependency lock, and ATT&CK commit.
2. Run the same predeclared primary model in every external condition. Use five repetitions with seeds 1103, 2207, 3301, 4409, 5519. If the endpoint cannot honor seeds, run five independently timestamped repetitions, mark seed control unavailable, and do not call them seeded replicates.
3. B1 may add one gate call, zero or one question, and (eligible cases only) one canonical answer. It may not add another agent, retrieval pass, synthesis call, or question.
4. Benchmark answers derived from withheld source use source_span (or documented analyst_adjudicated) and retain source IDs. Only an operational answer actually supplied by a person uses user_reported.
5. Log calls, input/output tokens, latency, answer length, failures, and estimated cost/energy where available. Truncation and context overflow remain observations.

## Frozen metric definitions

### Supported report claims

Gold claims are atomic units in the case JSON. Normalize whitespace and Unicode only. Match a predicted claim to at most one gold claim by:

1. exact normalized text; otherwise
2. semantic equivalence independently accepted by two blinded adjudicators, with a third resolving disagreement.

A match is a true positive only when its proposition is correct and every cited source-span/answer reference resolves and supports it at the stated uncertainty. An unmatched, contradicted, or ungrounded predicted claim is a false positive. An unmatched required gold claim is a false negative. Use maximum one-to-one matching before counts.

precision = TP / (TP + FP) and recall = TP / (TP + FN). If no claims are predicted while required gold claims exist, precision is 0. If both predicted and required-gold sets are empty, precision and recall are 1. If the recall denominator is zero but predictions exist, recall is 1 and those predictions determine precision. F1 = 2PR/(P+R) when P+R is greater than 0; otherwise F1 is 0.

### Gate and resolution

- **Necessity precision:** eligible asks targeting a genuinely absent, report-critical, answerable slot / all asked questions. Any question on a sufficient or explicitly-unknown control is unnecessary.
- **Necessity recall:** eligible cases with exactly one necessary question / all eligible cases.
- **Target-slot accuracy:** eligible asked questions assigned to the gold target_slot_id / eligible asked questions. If no eligible question is asked, report undefined and zero correct counts.
- **Resolution success:** the gate asks once for the gold slot, the canonical answer_id is accepted exactly once, and the answer is available to Stage 2 with its provenance intact.
- **Resolved-gap rate:** eligible cases with resolution success / all eligible cases under intention-to-treat.
- **Question burden:** questions per case, question characters/tokens, proportion with more than one question, and unnecessary-question rate separately for sufficient and explicitly-unknown controls.
- **Answer uptake:** affected claims with explicit answer-to-claim lineage and correct uncertainty / affected claims expected after clarification.

The prompt instructs one atomic fact, but atomicity is human-adjudicated: current runtime validation can reject empty, over-length, multiline, or multiple-question-mark output; it does not semantically prove that a single-mark question is non-compound.

### ATT&CK mapping

Score exact gold technique/sub-technique IDs with one-to-one set matching. Required mappings are positives; explicitly excluded mappings count as false positives if emitted. Report micro precision/recall/F1, macro case-level F1, exact-set accuracy, over-mapping count, and abstention accuracy. A mapping is supported only when its source-span or answer lineage resolves and entails the behavior.

### Recovery

For a higher-is-better score:

    recovery_pct = 100 * (score_b1_eligible_clarified - score_b0_eligible_masked)
                         / (score_b0_complete - score_b0_eligible_masked)

Compute recovery only when score_b0_complete - score_b0_eligible_masked is greater than 0. When the denominator is zero or negative, recovery is undefined; report the count, reason, and raw paired deltas. Do not clamp values below 0% or above 100%. Reverse signs first for lower-is-better metrics.

### Matched harm deltas

For sufficient and explicitly-unknown cases report paired B1-minus-B0 changes in supported-claim F1, ATT&CK false positives, unsupported claims, latency/tokens, and question burden. Report the effect for each of the seven scenario families plus the mean and median family effect. These gate-off pairs describe observed differences more directly than unmatched outputs, but H3 has no near-zero threshold, equivalence margin, confirmatory test, or equivalence test. The estimates cannot establish absence of harm or safety.

## Intention-to-treat failure handling

Every assigned B1 run remains in the primary analysis. A missing/extra/compound/wrong-slot question, unavailable canonical answer, invalid schema, refusal, timeout, overflow, empty report, or extra synthesis call is a failure. If no final report exists, all required claims/mappings are false negatives and emitted unsupported items remain false positives. If a fail-open report exists, score it as emitted. Do not replace a failed question with gold or silently rerun until favorable. Per-protocol summaries may be labeled exploratory only.

## Blinding and annotation

- Create gold before model outputs using [annotation_guide.md](annotation_guide.md).
- Two annotators score opaque, randomized outputs independently; a third adjudicates.
- Report scorers do not see condition, prompt, filename, latency, question transcript, or competing outputs.
- Gate scoring is a separate pass. Lock necessity, atomicity, answerability, and target-slot labels before revealing the complete case or canonical answer.
- Report raw agreement, Cohen's kappa for two-rater categorical labels, Krippendorff's alpha when ratings are missing/multi-rater, and adjudication rates.

## Statistical analysis and limited power

The inference unit is the CAM-LDS scenario family (inference_group), not a span, case, gap, simulation run, seed, or question. Average repetitions and all derived units within family before computing paired condition differences.

- H1 gate outcomes are confirmatory; report every numerator/denominator and family-level value for eligible and control cases.
- H2's primary endpoint is the family-level paired supported-claim F1 difference for b1_eligible_clarified minus b0_eligible_masked.
- For H2, enumerate all 2^7 = 128 cluster-level sign assignments for the exact two-sided paired randomization test.
- For H2, report the mean and median of the seven family effects and a 95% randomization interval obtained by inverting the same exact sign test. If discreteness yields an unbounded or non-unique interval, report that fact and all seven family effects rather than substituting an asymptotic CI.
- Apply Holm correction only across predeclared confirmatory secondary endpoints under H1 and H2. Exact ATT&CK outcomes under H2 are secondary.
- H3 matched harm deltas are descriptive only. Report all seven family effects, their mean and median, and raw case counts without a p-value, equivalence margin, equivalence test, or safety conclusion.

Seven clusters provide limited power and coarse attainable p-values. Null results cannot establish equivalence or safety. H3 is not designed or powered as an equivalence analysis, so small observed deltas cannot be called evidence of no harm. Positive H1/H2 results remain synthetic-family evidence, not real-enterprise effectiveness. The single NFI case is reported separately without inferential pooling.

## Leakage and artifact controls

- Hash and access-log sealed complete inputs, withheld spans, canonical answers, gold questions, reports, and ATT&CK labels.
- Prompt development uses development families only. Search prompts for case IDs, withheld strings, answer text, and gold technique IDs before test execution.
- The semantic validator must pass every case and enforce visible-span, withholding, answer-link, case-kind, and cross-file split invariants.
- Each run records case/schema version; dataset URL/version/license/hash; split_group; inference_group; ATT&CK commit; code and dirty-snapshot identifiers; prompt hashes; condition; model/artifact; seed support; decoding; hardware; UTC times; calls/tokens/latency/cost; gate/question/answer/provenance; Stage 1/2 hashes; raw output; parser; and failure status.

## Decision boundary

The study may claim only what executed fidelity and external tests support. It cannot infer real-world forensic reliability, analyst productivity, trust, or incident-response benefit without separate realistic deployment and user studies.
