> Scope note: this is an optional advanced methodology appendix. Use the [recommended Bachelor-facing plan](../cybercase-bachelor-improvement-study/README.md) for the thesis.

# CyberCase Report-Critical Clarification Gap Study

## Executive answer

The defensible Bachelor contribution is one bounded treatment, evaluated separately from baseline fidelity:

- **B0-reproduction** exactly reproduces the frozen two-stage NFI Crystal Clear method of [Dehing et al.](https://doi.org/10.1145/3785318.3785330) using its [official repository](https://github.com/NetherlandsForensicInstitute/local-llm-chat-report-benchmark), prompts, output schema, and Trace IDs. It adds no ATT&CK output and is a fidelity stratum only.
- **B0-external-adapted** uses the same extraction-then-synthesis pattern but declares every adaptation required for CAM-LDS-compatible evidence, a fixed external report schema, and exact ATT&CK evaluation. It is not called a faithful reproduction.
- **B1** is exactly B0-external-adapted plus one schema-gated, report-critical clarification opportunity before final synthesis. It may ask at most one question only when one answerable missing fact can change a required claim or ATT&CK mapping.

Evidence lineage is fixed measurement infrastructure in every external arm, not another treatment. The study measures necessity, target-slot accuracy, resolution, question burden, supported-claim change, ATT&CK change, and descriptive paired harm deltas on sufficient/explicitly-unknown controls. With seven families, those harm deltas support neither an equivalence test nor a safety claim. This package reports no B1 outcome.

[Gatto et al.](https://aclanthology.org/2025.acl-long.1226/) motivate careful follow-up evaluation but do not supply the cyber treatment: FollowupQ generates large medical question pools and RIM does not penalize extra questions. CyberCase instead tests one question and must count unnecessary or unanswerable questions.

## Artifact index

The package contains 16 files: this README plus the 15 artifacts below.

1. [research_gap.md](research_gap.md) — paper-by-paper evidence, adaptations, gap, and non-novelty boundary.
2. [project_inventory.md](project_inventory.md) — reconstructable dirty-snapshot code truth and line anchors.
3. [paper_story.md](paper_story.md) — bounded thesis, contributions, RQs, and hypotheses.
4. [claim_evidence_map.md](claim_evidence_map.md) — current/future evidence required for each claim.
5. [dataset_and_evaluation_plan.md](dataset_and_evaluation_plan.md) — frozen sources, roles, licenses, and derived-case design.
6. [evaluation_protocol.md](evaluation_protocol.md) — preregistered eight-row design, metrics, grouping, statistics, and failure rules.
7. [annotation_guide.md](annotation_guide.md) — gold construction and adjudication instructions for all three case kinds.
8. [dataset_manifest.csv](dataset_manifest.csv) — machine-readable ten-resource inventory.
9. [run_matrix.csv](run_matrix.csv) — one fidelity row and seven external condition rows.
10. [references.bib](references.bib) — verified paper and resource metadata.
11. [schemas/cybercase_eval_case.schema.json](schemas/cybercase_eval_case.schema.json) — Draft 2020-12 discriminated external-case contract.
12. [examples/cybercase_eval_case.example.json](examples/cybercase_eval_case.example.json) — fictitious eligible-masked case.
13. [examples/cybercase_eval_case.sufficient.example.json](examples/cybercase_eval_case.sufficient.example.json) — fictitious sufficient control.
14. [examples/cybercase_eval_case.explicitly_unknown.example.json](examples/cybercase_eval_case.explicitly_unknown.example.json) — fictitious explicit-unavailability control.
15. [scripts/validate_cases.py](scripts/validate_cases.py) — schema plus semantic/cross-file validator.

## Validate cases

From the repository root, use the repository Python environment:

```powershell
.\env_mitre\Scripts\python.exe deliverables\cybercase-report-followup-gap-study\scripts\validate_cases.py deliverables\cybercase-report-followup-gap-study\examples\*.json
```

Run its permanent valid-fixture and negative-mutation checks separately:

```powershell
.\env_mitre\Scripts\python.exe -B deliverables\cybercase-report-followup-gap-study\scripts\validate_cases.py --self-test
```

The validator checks the Draft 2020-12 schema plus unique IDs, references, offsets and exact quoted spans, visible/withheld-span rules, answer isolation and lineage, affected and unaffected claim states, explicit-unknown ATT&CK exclusions, case-kind constraints, and cross-file grouping. It exits nonzero and prints JSON paths when a case is invalid. The `-B` self-test command disables bytecode-cache creation.

## Explicit status and limitations

- The documents, schema, examples, validator, and run grid are implemented planning artifacts.
- No NFI rerun, CAM-LDS experiment, statistical test, analyst study, or effectiveness measurement has been performed here.
- Current CyberCase is an implementation vehicle, not B0-reproduction or B0-external-adapted. Its frontend report is client-side, demo-only, non-persistent, and unverified.
- The current follow-up pilot shows workflow feasibility on synthetic M365 fixtures only; it cannot support effectiveness or generality claims.
- CAM-LDS is synthetic Linux data with no benign activity. With seven scenario-family inference groups, power and attainable p-values are limited.
- A derived human-adjudicated masked-case layer is required because no audited open cyber dataset supplies incident evidence, a deliberately missing fact, an expert gold question, and a downstream report together.

## Next decision gate

Freeze the external schema, derived cases, scenario-family splits, primary model, prompts, and protocol before observing outcomes. Recompute NFI fidelity separately. Only then implement the isolated B1 gate and run the eight-row design.
