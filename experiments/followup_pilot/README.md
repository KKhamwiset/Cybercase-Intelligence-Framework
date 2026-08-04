# Follow-up Pilot

This isolated harness compares the persisted chat clarification positions. It is
research code, not a production chat, report, database, frontend, or RAG-service
feature.

## Conditions

- `no_followup` calls the existing RAG `/query` boundary once and never calls the
  follow-up policy.
- `post_rag_adaptive` is the explicit post-RAG baseline. It calls RAG first,
  evaluates the refactored case-fact policy, collects up to three controlled
  answers, and calls RAG again after each answer. `adaptive_followup` remains a
  backward-compatible alias so existing recorded result files remain loadable.
- `pre_rag_adaptive` evaluates the case-fact policy before every RAG call. A
  clarification question causes zero RAG calls for that decision; RAG is called
  only after the policy chooses `answer`, the policy fails open, or the maximum
  round is reached.

All adaptive methods use the production policy interface: the policy receives
only the original user request and prior user clarification exchanges. It never
receives a generated RAG answer or hidden fixture fields.

Every new result records `policy_position`, `policy_calls`, `rag_call_count`,
`questions` with their answers, `stopped_by`, and `latency_ms`; the detailed
`rag_calls` records are retained as well. Existing result files are not
rewritten and remain accepted through backward-compatible defaults.

## Controlled answer sheet

The case fixture intentionally hides only `affected_account` and
`initial_access`. During an adaptive run, the answer sheet is printed for the
human tester. For a question outside the answer sheet, enter:

```text
ไม่ทราบและไม่มีข้อมูลดังกล่าวในสำนวนที่มี
```

The runner also asks the tester to mark compound questions and identify which
controlled hidden field the question requested. Those annotations are used for
recovery metrics; no semantic matcher or user-simulation model is used.

The `m365_phishing_insufficient_001.json` fixture is a deterministic
insufficient-context case: the affected account is known, but the request asks
for one exact initial-access sub-technique while the distinguishing access
mechanism is omitted. Data exfiltration is explicitly unknown. Its fake
regression test verifies that pre-RAG clarification asks for the material
initial-access fact before making the RAG call.
The `m365_phishing_sufficient_001.json` fixture is the paired sufficient-context
case. It includes the phishing link, credential entry, affected account, and
unauthorized login evidence needed for the requested exact sub-technique. Its
regression test verifies that pre-RAG policy evaluation proceeds directly to one
RAG call without asking a clarification.
## Run the pilot

From the repository root, with Docker RAG service available and secrets loaded:

```powershell
doppler run --project env_cybercase_framework --config dev -- .\env_mitre\Scripts\python.exe -m experiments.followup_pilot.runner --case experiments/followup_pilot/cases/m365_phishing_001.json --method no_followup

doppler run --project env_cybercase_framework --config dev -- .\env_mitre\Scripts\python.exe -m experiments.followup_pilot.runner --case experiments/followup_pilot/cases/m365_phishing_001.json --method post_rag_adaptive

doppler run --project env_cybercase_framework --config dev -- .\env_mitre\Scripts\python.exe -m experiments.followup_pilot.runner --case experiments/followup_pilot/cases/m365_phishing_001.json --method pre_rag_adaptive

doppler run --project env_cybercase_framework --config dev -- .\env_mitre\Scripts\python.exe -m experiments.followup_pilot.runner --case experiments/followup_pilot/cases/m365_phishing_001.json --method all
```

JSON results are written to `experiments/followup_pilot/results/` unless
`--results-dir` is supplied. The `all` command creates new uniquely named
results and does not overwrite historical files.

## Blind manual evaluation

Supply a supported pair of result files. The evaluator randomizes them as
`System A` and `System B`, presents only final analyses and the common reference
checklist, collects all field scores, and reveals the mapping after scoring.

```powershell
.\env_mitre\Scripts\python.exe -m experiments.followup_pilot.evaluator --case experiments/followup_pilot/cases/m365_phishing_001.json --results <first.json> <second.json> --output experiments/followup_pilot/results/evaluation.json
```

Supported pairs are the historical `no_followup`/`adaptive_followup` pair, the
new `no_followup`/`post_rag_adaptive` pair, and the direct
`post_rag_adaptive`/`pre_rag_adaptive` comparison.

## Offline tests

```powershell
.\env_mitre\Scripts\python.exe -m pytest -q experiments/followup_pilot/tests
```

The tests inject fake RAG, policy, answer, input, output, and randomization
implementations. They do not require Anthropic, Qdrant, Neo4j, PostgreSQL,
Docker, or the RAG service.

## Limitations

- This is one synthetic case and cannot establish general effectiveness.
- The post-RAG baseline preserves the historical call position, while both
  runnable adaptive methods use the current case-fact-only production policy
  contract.
- Adaptive conditions include additional retrieval/model calls, so they measure
  the full clarification workflow rather than clarification text in isolation.
- Human answer-field and compound annotations can introduce judgment error.
