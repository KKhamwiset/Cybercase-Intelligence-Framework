# Research Gap

Status: literature/code synthesis and proposed experiment. No B1 effect has been measured.

## Dehing et al.: structured chat-report generation

Primary sources: [DOI 10.1145/3785318.3785330](https://doi.org/10.1145/3785318.3785330), [University of Groningen record](https://research.rug.nl/en/publications/structured-report-generation-using-local-llms-for-chat-based-digi/), and [official Apache-2.0 benchmark repository](https://github.com/NetherlandsForensicInstitute/local-llm-chat-report-benchmark).

### Method

- Stage 1 applies a fixed prompt to ten approximately-29k-token Crystal Clear chat parts and extracts case-relevant material with exact Trace IDs. One part is 29,864 tokens because conversation/device-boundary preservation can exceed the nominal split target.
- Stage 2 concatenates ordered Stage 1 summaries and synthesizes one structured investigative report.
- Five local models are compared with a Gemini 2.5 Pro generated reference. Released scripts recompute scoring and validate Trace IDs/equivalence.

### Reported result and boundary

Local models can be useful for entity/role extraction, but strict citation and chronological consistency remain weak. Outputs are provisional triage and require explicit validation before case-report use. Evidence comes from one fictitious chat corpus and a generated reference.

### Missing capability

The method does not expose a between-stage decision to ask for a report-critical missing fact, distinguish answerable gaps from explicit unavailability, or measure the downstream value/harm of one clarification.

## Gatto et al.: FollowupQ

Primary sources: [arXiv 2503.17509](https://arxiv.org/abs/2503.17509), [ACL 2025](https://aclanthology.org/2025.acl-long.1226/), and [public FB-Synth page](https://huggingface.co/datasets/PortalPal-AI/Followup-Q).

### Method

FollowupQ pools questions from specialist medical agents covering EHR reasoning, differential diagnoses, and message clarification, then de-duplicates/filters to a requested size. FB-Synth contains 250 samples and 2,336 expert questions; FB-Real is private.

### Reported result and metric boundary

The paper reports improvements on medical real/synthetic sets and reduced provider communications. Requested Information Match measures coverage of gold requested information but deliberately does not penalize additional questions. The task often produces dozens of candidates before filtering and expects multiple asynchronous questions, unlike a one-question cyber gate.

### Transfer limitation

It does not test whether one cyber incident fact is necessary for a fixed report claim, whether a question targets the correct report/ATT&CK slot, whether the answer is used with evidence lineage, or whether gate-on output improves over a matched gate-off report.

## Fidelity and external adaptation must remain separate

| Element | B0-reproduction | B0-external-adapted | B1 |
|---|---|---|---|
| Scientific role | NFI fidelity stratum | External gate-off comparator | Sole treatment |
| Source | Frozen Crystal Clear chat | CAM-LDS-compatible cyber evidence | Same external cases |
| Inputs | Frozen ten chat parts | Versioned evidence spans and three case kinds | Same, with gate seeing masked/control input |
| Output | Exact upstream report schema; no ATT&CK addition | Fixed adapted report, timeline, exact ATT&CK schema | Identical adapted output schema |
| Reference | Released generated reference and Trace-ID artifacts | Human-adjudicated claims/timeline/ATT&CK | Same external gold |
| Interaction | None | None | Zero or one report-critical question |
| Lineage | Upstream Trace IDs | Fixed measurement infrastructure | Same infrastructure plus canonical answer link |

Adaptations from the publication are source domain, identifiers, input contract, output schema, reference construction, prompt wording required by those contracts, and evaluation metrics. Because these are material, the CAM-LDS arm is never called a faithful reproduction.

## Code-to-paper gap matrix

| Requirement | Current CyberCase evidence | Gap for the study |
|---|---|---|
| B0-reproduction | No two-stage NFI report path exists. Backend calls only RAG `/query`; frontend report is local demo output. | Execute the frozen upstream benchmark separately. |
| External Stage 1/schema | Current chat worker runs a case-fact policy before RAG, not after evidence extraction against a report schema. | Build an isolated adapted research path. |
| One atomic fact | Policy prompt requests one fact; validation checks empty/length/newlines/question-mark count. | Semantic compoundness still needs annotation; runtime syntax does not enforce one topic. |
| One total question | Production permits up to three rounds. | B1 budget must hard-stop after one question. |
| No-question controls | Worker can proceed/fail open, but no three-kind research contract exists. | Encode sufficient and explicitly-unknown controls with no question/answer. |
| Evidence lineage | Demo IDs are generated candidates; retrieval context is process-local/TTL. | Persist immutable span, answer, claim, timeline, and ATT&CK references. |
| Causal comparison | Existing pilot compares workflow positions on one synthetic M365 fixture. | Use matched eight-row design and grouped external inference. |

## Novelty-safe combined gap

> Prior work separately supports two-stage forensic reporting and broad follow-up-question generation, but the audited literature and code do not evaluate a single report-critical clarification as the only treatment in a fixed external cyber report pipeline, with answerability-aware no-question controls, explicit answer-to-claim lineage, and downstream supported-claim/ATT&CK effects.

The defensible contribution is the treatment definition, discriminated case/evaluation contract, and matched effect measurement. B0-reproduction establishes fidelity but is not the external counterfactual. B0-external-adapted is the gate-off counterfactual but is openly adapted.

## What would not be novel

- Two-stage extraction and synthesis.
- LLM-generated forensic reports, timelines, citations, or ATT&CK mappings.
- Asking follow-up questions or adding a human-in-the-loop.
- Multi-agent orchestration or question pools.
- RAG, evidence provenance, abstention, or schema validation alone.
- Client-side report rendering or integrating the mechanism into CyberCase.
- Masking a field without showing a downstream matched treatment effect.

Nor would it be defensible to claim that one feasibility pilot establishes generality, that a generated reference is ground truth, that ATT&CK ontology objects are test cases, or that evidence lineage guarantees factual truth.
