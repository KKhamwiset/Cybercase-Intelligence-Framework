# Paper Story

## Working title

**Does One Bounded Clarification Improve Evidence-Grounded Cyber-Investigative Case-File Drafts?**

## One-sentence thesis

We study whether one reduced FollowupQ-inspired clarification before an unchanged Dehing-style case-file reporting baseline changes evidence-grounded report quality on preregistered incomplete investigative packets, and we measure target match and added cost.

## Task boundary

- **Inputs:** frozen multi-artifact cyber-investigative case-file packets with one preregistered finding removed.
- **Outputs:** provisional, examiner-verifiable report drafts; B1 also outputs one selected question and, only on a target match, a separately sourced supplemental investigator statement.
- **Supported settings:** six CFReDS Data Leakage gaps and two small CASE Owl transfer gaps, with paired B0/B1 execution.
- **Out of scope:** a new mechanism, faithful FollowupQ reproduction, final forensic conclusions, operational deployment, statistical generalization, and native Thai effectiveness.

## Problem gap

Two-stage LLM reporting work shows extraction followed by synthesis for forensic chat records, while follow-up-question work shows multi-perspective question generation and filtering in medical conversation. Neither establishes whether one bounded clarification helps evidence-grounded drafting from a multi-artifact cyber-investigative dossier.

## Technical challenge

- The case-file packet must preserve evidence identity across heterogeneous artifacts and report synthesis.
- The clarification must target information genuinely absent from the visible packet without seeing hidden gold.
- The B0 implementation must remain identical after the B1 insertion so paired differences are interpretable.
- Supplemental investigator information must remain distinct from source evidence, and the small correlated design permits descriptive conclusions only.

## Method insight

Treat clarification as a bounded pre-processing step that may add one explicitly sourced statement, then reuse the reporting baseline unchanged. This separates the question's information contribution from evidence extraction and report synthesis.

## Method summary

1. Freeze a complete case-file packet with dataset-neutral `evidence_id` and `source_locator` fields.
2. Create preregistered incomplete conditions while keeping target findings and answers hidden.
3. B0 performs two-stage extraction/synthesis and emits a provisional report draft.
4. B1 first generates candidates from entity/role, chronology, and evidence/citation perspectives; a bounded filter selects at most one question using visible evidence only.
5. After selection, a target match may release one separately identified `supplemental_investigator_statement`; the exact B0 then runs.
6. Score paired outputs for findings, claim support, citations, entity/timeline correctness, question quality, and cost.

## Planned contributions

- **Case-file adaptation of a published baseline:** dataset-neutral evidence identifiers and locators enable examiner-checkable drafting across heterogeneous packet artifacts.
- **Controlled one-step integration:** a reduced clarification step precedes an unchanged B0, isolating the practical treatment without claiming a novel method.
- **Transparent evaluation protocol:** preregistered gaps, hidden-gold controls, paired scoring, provenance rules, and cost reporting make the small study auditable.
- **Modest transfer check:** two CASE Owl gaps test whether observed behavior persists beyond the primary CFReDS packet without requiring a large raw corpus.

All contributions are planned until implementation and evaluation exist.

## Experimental evidence

The core evidence will be six CFReDS gaps, with two CASE Owl transfer gaps reported separately. Metrics are required-finding recall, evidence-supported claim precision, investigator-reported claim rate, unsupported-claim rate, evidence-reference coverage/source-locator accuracy, entity/timeline correctness, target-gap match@1, redundancy, answerability, latency, tokens, and calls. Three repeats are used if stochastic; deterministic inference is documented otherwise. No runs, scores, or headline numbers exist yet.

## Related-work positioning

Dehing et al. provide method provenance for two-stage extraction/synthesis; their NFI Crystal Clear chat benchmark is not this study's experimental dataset. Gatto et al. provide inspiration for multi-perspective candidate generation/filtering, but B1 is intentionally reduced and is not a faithful FollowupQ reproduction. CFReDS and CASE supply the case-file-oriented evaluation materials.

## Claims to make

- The paper can describe the implemented B0/B1 protocol and provenance controls exactly.
- It can report observed paired differences, question-target matches, and added costs for the tested frozen packets.
- It can report whether citations resolve to supporting source locations under examiner scoring.

## Claims to be careful about

- “Improvement” must name the metric, case, condition, and repeat aggregation.
- A supplemental investigator statement is reported information, not independently verified source evidence.
- CASE Owl is a small transfer check, not broad external validation.
- Any Thai translation is an English-origin translated condition.

## Claims to avoid

- A novel clarification or reporting mechanism.
- Faithful reproduction or superiority over FollowupQ or Dehing et al.
- Statistical significance, causal generalization, state of the art, operational forensic reliability, examiner replacement, or demonstrated Thai effectiveness.

## Reviewer risks

- Six primary gaps come from one case and are not independent samples.
- Packet construction and masking may simplify naturally incomplete investigations.
- Manual support and timeline judgments may disagree despite double scoring and adjudication.
- A match-based controlled answer may overestimate real investigator availability or answer quality.
- Dataset reuse terms and artifact-specific redistribution rights must be resolved before release.
