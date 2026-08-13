# B0/B1/B2 Repeatability Pilot Summary

This document summarizes the controlled `case-001` repeatability pilot saved as run `20260807T145601Z_2f1a3210`. It reports observations from these three repeats only. It does not claim statistical significance or general effectiveness.

## 1. Exact run configuration

- Branch: `experiment/b0-b1-b2-report-architecture`
- Experiment code SHA: `513ccfed7881432d7e170e795cfcdbac453bee46`
- Original experiment base SHA: `ee6d8b47967937f55e44a422b13a88ded4b2c389`
- Provider/model: Anthropic / `claude-haiku-4-5-20251001`
- Case: `case-001`; case SHA-256 `390a369369ac5e23430a92c0917d576d34a6e151d842def3c7844c5bebc520e3`
- Conditions/repeats: B0, B1, and B2, each repeated three times in one official invocation
- Temperature: `0.0`
- Extraction/report output limits: `4096` / `8192` tokens
- Context window / B1 maximum chunk size: `32000` / `256` estimated tokens
- B1 deterministic chunk count: 2
- Request timeout: 90 seconds
- Relationship IR: `relationship_ir_v1`
- Relationship extraction prompt: `relationship_extraction_prompt_v4`
- Report schema: `baseline_report_v1`
- Report prompt: `report_architecture_report_prompt_v2`
- Extraction/report enforcement: `tool_json_local_validation` / `tool_json_local_validation`
- Extraction/report transport protocols: `anthropic_relationship_extraction_transport_v5` / `anthropic_report_transport_v1`
- Active extraction/report contract hashes: `030b22b7d9b215b05a9accd029868c25093dc1316380b4e4a929e173528e0563` / `0438f1c95e8830abbfb78b168046eb23c023b9c5f37ff2ce867906a1c509bc09`
- Experiment/artifact protocols: `report_architecture_b0_b1_b2_v7` / `report_architecture_artifacts_v1`

Protocol v7 changes only provider-response artifact persistence: exact HTTP entity bytes, HTTP status, response availability, and response hashes are retained for successful and failed calls. Prompts, schemas, request transports, model, decoding, chunking, merge behavior, and condition data flow remain frozen from v6.

The run was one invocation with no model-backed preflight, no retry, no fallback, and no model substitution. The repository manifest reports `dirty: true` because unrelated user-owned backend/frontend changes existed; the experiment subtree itself was committed and clean at the recorded experiment SHA.

## 2. Validity and failure results

| Condition | Valid / attempted | Official model calls | Observed result |
|---|---:|---:|---|
| B0 | 3 / 3 | 3 | All three one-call reports passed local structural validation. |
| B1 | 0 / 3 | 3 | All three first-chunk HTTP 200 outputs failed local validation with `relationship_ir_placeholder_id_invalid`; chunk 2, merge, and report generation were not attempted. |
| B2 | 0 / 3 | 3 | Repeats 1-2 returned HTTP 200 but failed local validation with `reference_relationship entity_invalid`; repeat 3 returned HTTP 400 `invalid_request_error` because the Anthropic credit balance was too low. No B2 report was attempted. |

Overall, 3/9 condition repeats produced validated final reports. There were nine official calls in total. The short-circuit behavior is part of the frozen method: failed extractions were retained and were not replaced or retried.

The B2 repeat-03 provider body states that the credit balance was too low. This is a provider/account failure, separate from the semantic/structural failures in the HTTP 200 outputs.

## 3. Resource observations

Token statistics use provider-reported usage. B2 repeat 3 did not return usage, so B2 token statistics cover the two HTTP 200 model outputs (`n=2`). Latency covers all three attempted repeats, including the short HTTP 400 response.

| Condition | Calls | Input tokens, mean (min-max) | Output tokens, mean (min-max) | Latency, mean (min-max) |
|---|---:|---:|---:|---:|
| B0 | 3 | 2,521 (2,521-2,521), n=3 | 2,175.667 (2,019-2,381), n=3 | 16.224 s (15.107-17.400) |
| B1 | 3 | 3,361 (3,361-3,361), n=3 | 1,068 (1,061-1,072), n=3 | 6.648 s (6.419-6.976) |
| B2 | 3 | 3,296 (3,296-3,296), n=2 | 1,619 (1,608-1,630), n=2 | 6.037 s (0.629-8.777) |

B1 used 65 more input tokens than B2 for each observed first extraction call, about 2.0%. This is not a complete B1-versus-B2 architecture-cost comparison: every B1/B2 repeat stopped after its first extraction call, and the short B2 provider error depresses its all-attempt latency mean. Across the two B2 HTTP 200 calls, mean extraction latency was 8.741 seconds.

B0 completed a report in one call per repeat. B2 also made one call per repeat, but those were extraction calls and no report was produced; therefore the observed B0/B2 latency and token totals do not compare equivalent completed outputs.

## 4. Within-condition stability observations

### B0

- Structural validity was stable: 3/3 reports had all seven required sections and valid authorized references.
- The core reported facts were semantically stable: the suspicious-message report, reported USD 4,200 transfer to ACCT-77, HOST-7 account access, and explicit ownership/control/attribution uncertainty appeared in all repeats.
- Exact output was not stable. Claim counts were 7, 8, and 9; limitation counts were 8, 7, and 11; all raw-response hashes and serialized report hashes differed.
- All claim source references resolved to `SRC-001` through `SRC-003`, and the only MITRE reference was the authorized frozen `T1566` candidate. B0 has no IR, so its reports contained no evidence-ID or event-ID references; its traceability was source-level.
- Uncertainty was generally preserved, but free-form section prose was not uniformly evidence-bound. In repeat 3, the technical section calls the access "unauthorized" and suggests "credential compromise or account takeover," neither of which appears in the case sources. Repeat 1 also says a financial transfer "occurred" where the source says it was reported. These examples passed structural validation because the validator checks report shape and claim references, not entailment of every paragraph sentence.

### B1

All three raw first-chunk candidates had the same structural content before local validation rejected them:

- 2 entities: `employee@example.org` and `ACCT-77`
- 2 evidence items and 2 events
- 1 reported `transferred_funds_to` relationship
- 1 missing relationship and 1 missing-information item
- Valid references to the authorized chunk sources

Every repeat represented the unknown controller of ACCT-77 as `object_id: "<UNKNOWN>"` in `MISSING-REL-001`. The frozen validator forbids placeholder IDs, producing `relationship_ir_placeholder_id_invalid` in 3/3 B1 repeats. Warning wording varied, but the entities, events, evidence, relationship, missing relationship, and failure code were stable.

### B2

Repeats 1 and 2 produced closely matched raw candidate IRs before validation failed:

- 3 entities: `employee@example.org`, `ACCT-77`, and `HOST-7`
- 3 evidence items and 3 events
- 3 relationships
- 1 missing relationship and 3 missing-information items
- Stable entity names/types, event actors/targets, relationship predicates, and authorized source references

Both candidates set `REL-001.object_id` to evidence ID `EV-001` for an account `received` relationship. A relationship endpoint must be an entity ID, so both failed with `reference_relationship entity_invalid`. Both also encoded `HOST-7 owned_by employee@example.org` as a missing relationship even though the source only says ownership is unknown; the selected endpoint is not established by the source. Minor variance appeared in timestamp formatting (`2026-08-01T10:20:00` versus a `Z` suffix), missing-information wording, evidence wording, and warnings.

B2 repeat 3 produced no candidate IR because the provider returned the recorded HTTP 400 credit-balance error.

## 5. B1 chunk-fragmentation observations

The deterministic B1 chunk plan was identical across repeats (same `chunks.json` SHA-256, `777e3c9bb4f5593ca45162037022d8369fe7eda01a993aacc789028a59145963`). Chunk 1 contained `SRC-001` and `SRC-002`; chunk 2 contained `SRC-003`.

Because every repeat failed while validating chunk 1, chunk 2 was never called and deterministic merge never ran. Consequently, the earlier cross-chunk duplicate/generic `employee account` behavior could not be evaluated in this pilot. It was not observed, but absence cannot be inferred from a path that never reached the boundary or merge.

## 6. B2 run-to-run variance observations

Among the two available B2 model outputs, the major structure and the same invalid relationship endpoint repeated. The exact prior `UNKNOWN_OWNER` / `UNKNOWN_CONTROLLER` entity behavior did not recur in either of those two outputs. The third repeat had no semantic output due to the provider error. Therefore the specific `UNKNOWN_*` behavior occurred in 0/2 available B2 model outputs, not 0/3 completed extractions, and this pilot does not show that the behavior has disappeared.

Legitimate unknowns were retained as three semantically equivalent missing-information items in both available candidates. However, the additional `owned_by` missing relationship supplied a specific employee-account endpoint that the source did not establish.

## 7. B0 efficiency observations

B0 was the only condition to produce final reports in this run and required one model call per validated report. Its fixed input count was lower than either first extraction request. The pilot therefore observed high completion efficiency for B0 under this case and run.

That observation cannot establish end-to-end superiority. B1 and B2 did not reach report generation, so their normal total call, token, and latency costs were not observed. B0 source references were valid but coarse; the two raw B2 candidates contained richer evidence/event/source structure, yet that structure was not usable because the IRs failed validation.

## 8. Known `support_type` instrumentation issue

`support_type` was not used as a comparative metric. B0 again labeled many source-grounded claims `extraction_candidate` even though B0 has no extraction stage. No B1/B2 report was produced in this run, so the previously observed B2 labeling behavior could not be reassessed. Grounding observations above are based on resolvability to authorized source, evidence, event, and MITRE references, not on generated `support_type` labels.

## 9. Methodological limitations

- Three repeats of one synthetic controlled case are insufficient for statistical inference or generalization.
- There are no gold labels, blinded human ratings, or independent semantic adjudicators.
- B1 never reached its second chunk, merge, or report; B2 never reached report generation. Comparative end-to-end report quality and normal architecture cost are therefore unobserved.
- Local validation reports the first encountered failure. Other semantic issues may remain behind that first failure.
- Invalid IR candidates are retained inside exact raw provider envelopes, but they are intentionally not promoted to parsed/validated IR artifacts.
- The B2 credit-balance failure reduced semantic coverage to two model outputs and made its all-attempt latency mean misleading.
- B0 paragraph prose can contain claims not separately represented in the structured `claims` array, limiting what structural validation proves.
- Fixed temperature and prompts do not imply deterministic outputs; B0 content and output-token counts varied.
- The artifact protocol was versioned before this run to preserve exact successful and failed HTTP bodies. This did not change the experimental request or generation methodology, but it means this run's artifact protocol is v1/v7 rather than the previous pilot's v6 persistence behavior.

## 10. What is justified to say from this pilot

- B0 produced structurally valid reports in 3/3 repeats under this frozen configuration.
- B0 preserved the core case facts and uncertainty across repeats, while report detail and some unsupported free-form hypotheses varied.
- B1 repeated the same forbidden-placeholder failure in 3/3 first-chunk outputs.
- B2 repeated the same invalid relationship endpoint in both available semantic outputs; one additional repeat failed at the provider/account layer.
- The prior B1 cross-chunk duplication behavior was not measurable because no B1 repeat reached chunk 2 or merge.
- The prior B2 `UNKNOWN_*` entity form was not seen in the two available B2 outputs, but a different unsupported unknown-endpoint relationship appeared in both.
- The result warrants further controlled evaluation; it does not establish a winner.

## 11. What is not justified to say

This pilot does not justify saying that B2 is superior, that chunking causes hallucination, that relationship-first generation is proven better, that B0 is semantically reliable, that temperature 0 is deterministic, that the B1 duplicate behavior is gone, or that the B2 `UNKNOWN_*` behavior is fixed. It also does not support significance claims or general claims about cybercrime reports.

## 12. Recommended next experimental step

After restoring sufficient Anthropic credit, run a separately identified follow-up using the same pinned Haiku 4.5 model and frozen v7 request methodology, with no retries or tuning, to obtain provider-complete B1/B2 repeats. Preserve this run unchanged. If the repeated schema failures remain, preregister a new versioned experiment that evaluates endpoint/unknown representation changes on additional held-out cases; do not retrofit those changes into this pilot.

## Artifact verification

All nine repeat directories contain their expected runtime/input artifacts. Every call marked as having a provider response has a corresponding raw body whose byte-level SHA-256 matches `runtime.json`; the audit found zero missing-artifact or hash errors. Empty report-response files in failed B1/B2 repeats explicitly represent stages that were not attempted, as confirmed by their runtime call records.
