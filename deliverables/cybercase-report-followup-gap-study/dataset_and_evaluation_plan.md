# Dataset and Evaluation Plan

Status: audited prospective plan, 2026-08-04. No model experiment or effectiveness result is reported.

## Two data roles

The study does not force unlike resources into one baseline:

1. **NFI Crystal Clear** is mandatory only for B0-reproduction fidelity. It retains the upstream inputs, prompts, report schema, Trace IDs, and metrics; no ATT&CK field is added.
2. **CAM-LDS-compatible external cases** support the B0-external-adapted versus B1 experiment. They use the package's fixed external report/ATT&CK schema and therefore are explicitly adapted, not a faithful Dehing reproduction.

No audited open cyber dataset supplies incident evidence, a deliberately missing report-critical fact, an expert gold follow-up question, and a downstream report together. The external arm therefore requires a derived human-adjudicated layer governed by [annotation_guide.md](annotation_guide.md), the [Draft 2020-12 schema](schemas/cybercase_eval_case.schema.json), and [semantic validator](scripts/validate_cases.py).

## Audited resources

| Resource | Verified access/license | Frozen snapshot and scale | Role/decision | Limitations |
|---|---|---|---|---|
| NFI Crystal Clear benchmark | [Repository](https://github.com/NetherlandsForensicInstitute/local-llm-chat-report-benchmark), Apache-2.0 | `5554ef79a0bce3342fb827da2511366ea71b7390`; one fictitious chat case; ten approximately-29k-token parts, one 29,864 due to boundary preservation | **Core fidelity.** Recompute released artifacts and freshly run one predeclared primary model using the exact upstream schema. | Single fictitious case; Gemini-generated reference; no external validity or clarification effect. |
| CAM-LDS v2 | [Zenodo](https://zenodo.org/records/18861762), DOI [10.5281/zenodo.18861762](https://doi.org/10.5281/zenodo.18861762), CC-BY-4.0 | Record 18861762; 7 scenario families, 34 runs, 13 tactics, 81 techniques; 7.4 GB full, 213.8 MB filtered, 535.9 MB raw manifestations | **Core external evidence/timeline evaluation.** `inference_group` and `split_group` are scenario family. | Synthetic Linux and no benign activity; derived gaps/questions/reports need adjudication. |
| CTID Attack Flow | [Repository](https://github.com/center-for-threat-informed-defense/attack-flow), Apache-2.0 | `1f0082445e71c712771d21f893d2dfe6fd8524a8`; **41 `corpus/*.afb` files** at the pinned commit | **Core supplement** for sequence/narrative annotation. | Count is scoped to `corpus/*.afb`, not all repository `.afb` files; flows are curated representations, not raw evidence. |
| CTID TRAM | [Repository](https://github.com/center-for-threat-informed-defense/tram), Apache-2.0 | `f29793d8d665f7f552898696e00065ef24a29a20`; multi-label 19,178 rows/4,070 positive/151 documents/50 labels; single-label 5,089 rows | **Optional** CTI-to-ATT&CK/abstention supplement. | Snippets from the same document are not independent incidents. |
| MITRE ATT&CK STIX | [Repository](https://github.com/mitre-attack/attack-stix-data), ATT&CK Terms | `a6c366439edee3a87b79cf90dc0b93f5d7975956` | **Core ontology only** for exact IDs/names/tactics. | Never count ontology objects as test cases. |
| FollowupBench FB-Synth | [Public dataset page](https://huggingface.co/datasets/PortalPal-AI/Followup-Q), CC-BY-NC-4.0 | Resolve/hash revision at acquisition; 250 samples/2,336 expert questions | **Optional transfer-only** atomicity/answerability diagnostic. | Medical, non-commercial, multi-question burden; FB-Real private. Public artifact/license independently verified, not downloaded in this audit. |
| Splunk Attack Data | [Repository](https://github.com/splunk/attack_data), Apache-2.0 | Resolve commit; over 9 GB full LFS payload | **Optional** selective telemetry holdout. | Mostly atomic-technique captures; group common simulations. |
| Splunk BOTSv3 | [Repository](https://github.com/splunk/botsv3), CC0-1.0 | Resolve commit/checksum; 320.1 MB pre-indexed Splunk | **Optional phase two** full-incident telemetry. | Legacy Splunk/add-ons and new gold required. |
| AIT Alert Data Set | [Zenodo](https://zenodo.org/records/8263181), DOI [10.5281/zenodo.8263181](https://doi.org/10.5281/zenodo.8263181), CC-BY-4.0 | Record 8263181 version 1; 8 scenarios/2,655,821 alerts | **Optional** noisy-alert ask-versus-abstain supplement. | Synthetic alerts; reconstruction and new gold required. |
| OTRF Security-Datasets | [Repository](https://github.com/OTRF/Security-Datasets) | No approved snapshot/license | **Excluded** until repository/dataset licensing inconsistency is resolved. | Availability is not permission. |

The machine-readable inventory is [dataset_manifest.csv](dataset_manifest.csv).

## External case kinds

- **eligible_masked:** immutable source plus complete and masked input variants, one decision target, one expected question, and one canonical controlled answer. The answer is not embedded in either input.
- **sufficient:** one sufficient input, expected `proceed`, no target gap, no question, and no controlled answer.
- **explicitly_unknown:** one input containing a source-linked unavailability statement, expected `proceed`, a target slot that must be qualified/abstained, no question, and no controlled answer.

Every case records `split_group` and `inference_group`. For CAM-LDS both are set to the scenario family so all runs and derived gaps from a family remain in one development/test split and are averaged before inference.

## Derived-case procedure

1. Freeze source files/hashes, license, ATT&CK commit, and scenario-family grouping.
2. Define one incident/run evidence boundary and exact spans with offsets into immutable `source_text`.
3. Adjudicate atomic report claims, timeline events, and exact ATT&CK mappings before model outputs.
4. For eligible cases, remove exactly one answerable fact that can change an affected claim or mapping. Record withheld spans, target slot, expected question, canonical answer/provenance, affected claim IDs, and expected states. Unaffected claims must be `retain_supported` across complete/masked/clarified states.
5. For sufficient controls, retain all required evidence and encode no target/question/answer.
6. For explicitly-unknown controls, retain a visible unavailability span and encode no question/answer; affected claims must qualify or abstain.
7. Validate schema and semantic invariants. Keep complete text, withheld spans, answers, and gold sealed from gate-time inputs.

Evidence lineage is held fixed in all external rows. It is measurement infrastructure, not an ablation or treatment.

## Acquisition and release record

For each resource log URL, resolved commit/record, license text/hash, selected paths, content checksums, timestamp, transformation commit, exclusions, and final unit counts. If a frozen snapshot cannot be acquired, stop that arm rather than silently substituting a moving branch.

Release license-permitted cases, validator, prompt/model/environment hashes, run manifests, raw outputs, scoring code, annotations, agreement/adjudication logs, and deviations. The eight-row design and limited seven-family inference are specified in [evaluation_protocol.md](evaluation_protocol.md).
