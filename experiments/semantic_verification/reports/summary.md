# Offline Semantic Verification Benchmark Summary

- Schema version: 2.0
- Seed: 314159
- Cases: 100
- English cases: 50
- Thai cases: 50
- Verification pairs: 800
- Supported pairs: 400
- Unsupported pairs: 400
- Positive gold-fact slot coverage: 100.0%

## Corruption counts

- actor_swap: 50
- target_swap: 50
- predicate_swap: 50
- timestamp_shift: 50
- negation_flip: 50
- certainty_strengthening: 50
- causality_insertion: 50
- attribution_insertion: 50

## Scenario counts

- email_execution: 25
- forwarded_attachment: 25
- mail_endpoint_review: 25
- received_document: 25

## Narrative template counts

- en-layout-1: 13
- en-layout-2: 13
- en-layout-3: 12
- en-layout-4: 12
- th-layout-1: 12
- th-layout-2: 12
- th-layout-3: 13
- th-layout-4: 13

## Positive gold-fact slots covered

- rel-001
- rel-002
- rel-003
- rel-004
- rel-005
- rel-006
- rel-007
- rel-008
- rel-009
- rel-010
- time-001
- time-002
- time-003
- time-004

## Integrity failures

- None

## Limitations

- Cases and labels are synthetic fixtures created from deterministic structured facts.
- Construction validation proves agreement with deterministic proposition renderers, not free-form language understanding.
- No forensic, deployed-system, or model-quality conclusion can be drawn from this dataset.

This is a fixture-construction validator, not a semantic verifier and not a model-quality result.
