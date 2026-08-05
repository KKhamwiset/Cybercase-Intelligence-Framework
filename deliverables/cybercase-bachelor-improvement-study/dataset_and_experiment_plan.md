# Dataset and Experiment Plan

## Source selection

| Source | Role | Decision |
|---|---|---|
| [NIST CFReDS Data Leakage Case](https://cfreds-archive.nist.gov/data_leakage_case/data-leakage-case.html) | Primary case | Use its scenario, exhibit/acquisition records, hashes, 60 questions, and public answer key to prepare one frozen multi-artifact packet and six missing-finding conditions. Link to raw images; do not redistribute them. |
| [CASE Owl Trafficking](https://caseontology.org/examples/owl_trafficking/) | Small transfer | Use the narrative and combined JSON-LD for mandate, provenance, exhibit, entity, and timeline checks. Prepare two gaps; the approximately 223 GB original raw corpus is not required. |
| [EvidenceForge v1.14.0](https://github.com/Cisco-Talos/EvidenceForge/releases/tag/v1.14.0) | Optional robustness only | MIT-licensed synthetic telemetry may be used only after the core study. It is not a core dataset or contribution. |
| NFI Crystal Clear | Related work/method provenance only | Reject as experimental data because chat transcripts do not represent a multi-artifact investigative dossier. |
| [Thai Police Open Data](https://opendata.thaipoliceonline.go.th/) | Motivation only | Aggregate statistics are not case-level evidence and cannot support the experiment. No verified open Thai dossier corpus was found. |

Before redistribution, record exact source versions and item-level rights. NIST's general reuse guidance covers NIST-created public information, but embedded third-party material may have separate rights; do not call the entire CFReDS bundle unconditionally public domain. Record CASE/CASE Owl terms before redistributing derivatives, and separately cite [Digital Corpora's scenario/metadata terms](https://digitalcorpora.org/about-digitalcorpora/terms-of-use/) where applicable. See [dataset_source_manifest.json](dataset_source_manifest.json).

## Frozen packet contract

Prepare one complete packet per case before making incomplete conditions. Each packet contains:

- case ID, mandate/scenario, and packet version;
- exhibit register and acquisition/integrity records;
- evidence artifacts represented as `evidence_id`, `artifact_type`, `source_locator`, `content`, and provenance;
- examiner-prepared required findings and their valid supporting locations, stored as hidden evaluation gold.

`source_locator` is dataset-neutral and may identify a file path, volume, table/row, record offset, page/paragraph, or JSON-LD node. It must be specific enough for an examiner to recover the cited source. Preserve original source hashes and also hash the frozen packet.

## Missing-finding conditions

Create **six preregistered CFReDS conditions**, balanced where possible across entity/role, chronology, and evidence/citation gaps, plus **two CASE Owl transfer gaps**. For each condition, remove one material required finding and every visible item that directly reveals it, while leaving the rest of the packet unchanged. Record outside model-visible inputs:

- `gap_id`, case ID, packet hash, and affected required finding;
- the exact removed evidence IDs/locators;
- acceptable question targets stated as semantic predicates, including allowed paraphrases;
- a minimal answer and its provenance; and
- the rule for whether that answer resolves the gap.

Gold answers, target predicates, and source locations remain hidden until after B1 selects its question. A matched answer is added only as a separate `supplemental_investigator_statement`; it is never inserted into or disguised as an original exhibit.

## Paired conditions and controls

| Condition | Processing |
|---|---|
| B0 | Incomplete frozen packet -> unchanged two-stage extraction/synthesis |
| B1 | Same incomplete packet -> bounded clarification -> optional separately sourced supplemental statement on a target match -> exact B0 |
| Complete-packet reference (optional) | Complete frozen packet -> B0; descriptive recoverability reference only |

Match B0/B1 on case, gap, model/version, prompt version, report schema, decoding, context budget, and repeat/seed. Use three paired repeats when stochastic. If deterministic, run once and document the provider/settings and repeat check used to establish determinism. The question generator/filter sees no hidden gold.

## Preregistered metrics

- **Required-finding recall:** required findings present and correct divided by all preregistered required findings.
- **Evidence-supported claim precision:** checkable report claims supported by a resolvable original exhibit divided by all checkable report claims.
- **Investigator-reported claim rate:** checkable report claims supported only by a separately identified supplemental investigator statement divided by all checkable report claims. Report this separately; it is not forensic evidence support.
- **Unsupported-claim rate:** checkable claims lacking valid support, including contradicted claims, divided by all checkable report claims.
- **Evidence-reference coverage:** evidence-supported claims with at least one cited `evidence_id` and `source_locator` divided by all evidence-supported claims.
- **Source-locator accuracy:** citations that resolve to a location supporting the attached claim divided by all citations.
- **Entity correctness:** preregistered entity, identity, and role assertions reported correctly.
- **Timeline correctness:** preregistered events, timestamps, and ordering relations reported correctly.
- **Target-gap match@1 (B1):** whether the one selected question matches any preregistered acceptable target.
- **Redundancy and answerability (B1):** fixed 0-2 rubrics, with exact anchors preregistered before runs.
- **Cost:** end-to-end latency, input/output tokens, and model calls, with unavailable provider fields shown as missing rather than zero.

## Scoring and analysis

Blind scorers to condition labels where practical. Score every raw primary output before adjudication. If feasible, two scorers independently score all paper-primary reports and questions; report exact agreement for discrete rubric items, agreement on claim-support labels, and all adjudicated changes. Keep the original scores.

Report every gap and repeat, then aggregate gaps **within each case**. Present CFReDS and CASE results separately and give descriptive paired B1-minus-B0 differences only; do not treat the eight gaps as independent cases and do not run significance tests. The optional complete-packet reference is not a second baseline.

## Language condition

The sources are English. They do not establish Thai effectiveness. If time permits, add a human-verified translation of a frozen packet that preserves evidence IDs, timestamps, names, hashes, paths, and technical terms. Report it as a **translated condition**, not a native Thai corpus, and never combine it with the English core result.

## Required future artifacts

The experiment must later preserve source/version records, packet builders, packet hashes, preregistration, prompts, model settings, raw outputs, token/call logs, scorer sheets, agreement/adjudication logs, and result tables. None exists in this planning package; no result may be inferred from current CyberCase application or pilot output.
