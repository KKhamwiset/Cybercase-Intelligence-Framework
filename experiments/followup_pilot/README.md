# Adaptive Follow-up Pilot

This isolated one-case harness compares the existing RAG `/query` behavior with
and without the backend-owned adaptive clarification policy. It is research
code, not a production chat, report, database, or frontend feature.

## Conditions

- `no_followup` sends the frozen Thai incomplete case to the existing
  `request_rag` boundary exactly once and never invokes the policy.
- `adaptive_followup` sends that same initial query, evaluates the existing
  `AnthropicFollowUpPolicy`, collects up to three controlled human answers,
  rebuilds each query with the existing `build_clarified_query`, and calls RAG
  again. A policy exception fails open to the latest RAG answer and is recorded
  as `policy_failure`.

Both conditions use the currently configured RAG service and model settings.
`--rag-model` is only a result metadata label; it does not alter execution.

## Controlled answer sheet

The case fixture intentionally hides only `affected_account` and
`initial_access`. During an adaptive run, the answer sheet is printed for the
human tester. The policy receives only the original incomplete query, prior
human-entered clarification exchanges, and the latest RAG answer; it never
receives `hidden_answers` automatically.

For a question outside the answer sheet, enter:

```text
ไม่ทราบและไม่มีข้อมูลดังกล่าวในสำนวนที่มี
```

The runner also asks the tester to mark compound questions and identify which
controlled hidden field the question requested. Those manual annotations are
used for recovery metrics; no semantic matcher or user-simulation model is
used.

## Run the pilot

From the repository root, with Docker RAG service available and secrets loaded:

```powershell
doppler run --project env_cybercase_framework --config dev -- .\env_mitre\Scripts\python.exe -m experiments.followup_pilot.runner --case experiments/followup_pilot/cases/m365_phishing_001.json --method no_followup

doppler run --project env_cybercase_framework --config dev -- .\env_mitre\Scripts\python.exe -m experiments.followup_pilot.runner --case experiments/followup_pilot/cases/m365_phishing_001.json --method adaptive_followup

doppler run --project env_cybercase_framework --config dev -- .\env_mitre\Scripts\python.exe -m experiments.followup_pilot.runner --case experiments/followup_pilot/cases/m365_phishing_001.json --method all
```

JSON results are written to `experiments/followup_pilot/results/` unless
`--results-dir` is supplied.

## Blind manual evaluation

Supply one result from each condition. The evaluator randomizes them as
`System A` and `System B`, presents only final analyses and the common reference
checklist, collects all field scores, and reveals the mapping after scoring.

```powershell
.\env_mitre\Scripts\python.exe -m experiments.followup_pilot.evaluator --case experiments/followup_pilot/cases/m365_phishing_001.json --results <no-followup.json> <adaptive.json> --output experiments/followup_pilot/results/evaluation.json
```

Allowed field labels are `correct_supported`, `missing`, `incorrect`, and
`unsupported`. The evaluator calculates completeness, hidden-field recovery,
final hidden-field utilization, question count, exact duplicate count,
compound count, and unsupported-field count.

## Offline tests

```powershell
.\env_mitre\Scripts\python.exe -m pytest -q experiments/followup_pilot/tests
```

The tests inject fake RAG, policy, answer, input, output, and randomization
implementations. They do not require Anthropic, Qdrant, Neo4j, PostgreSQL,
Docker, or the frontend.

## Limitations

- This is one synthetic case and cannot establish general effectiveness.
- The adaptive condition includes additional retrieval/model calls, so it
  measures the full clarification workflow rather than clarification text in
  isolation.
- Human answer-field and compound annotations can introduce judgment error.
- The current production policy JSON schema requires a non-empty `question`,
  while the production Pydantic model requires an empty question for
  `action="answer"`. This harness does not alter that production contract. A
  live answer-decision validation failure is preserved as `policy_failure` and
  fails open to the latest RAG answer.
- The evaluator is label-blind, but differences in final analyses may still
  allow a human evaluator to infer which system received clarification.
