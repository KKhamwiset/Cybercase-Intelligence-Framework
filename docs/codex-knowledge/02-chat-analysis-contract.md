# Chat Analysis Contract

## Main Case Analysis module

The internal service is `backend/app/services/case_analysis/service.py`.

```python
await request_case_analysis(
    mode="case_overview" | "question_answer",
    case_state_json=validated_case_state,
    analysis_context=grounding_snapshot,
    question=None | user_question,
)
```

Current contract properties:

- Prompt version: `main_case_analysis_v2`.
- `AnalysisMode` is an explicit `Literal["case_overview", "question_answer"]`;
  the module does not infer its task from whether `question` is present.
- `case_state_json` is the authoritative, validated Case State input.
- `analysis_context` contains already-persisted/retrieved context and MITRE
  rows; the module does not retrieve, extract, classify intent, mutate state,
  or generate a report.
- The backend maps initial analysis to `case_overview` with `question=None` and
  ASK to `question_answer` with the exact non-empty user question.
- Both modes use the same `MainCaseAnalysisService`, configured core model,
  provider request path, and response parser. Only the task prompt changes.
- Inputs are defensively copied before prompt construction. The module is
  read-only over Case State.
- Provider output is parsed across supported response envelopes and rejects
  empty, invalid, refused, or truncated analysis responses.
- The system prompt asks for concise output under 1,200 output tokens and no
  more than five short sections. The runtime output ceiling is configured by
  `settings.chat_ask_max_output_tokens`.

## Trust boundary

The prompt distinguishes three authorities:

1. Canonical Case State: reported facts, provenance, relationships, timeline,
   and epistemic status.
2. Retrieved/MITRE context: external technical knowledge, never a case fact.
3. Previous analysis: continuity only, never evidence.

Suspected, contradicted, or not-established relationships must remain qualified.
The model must not invent actors, causality, timestamps, identifiers, mappings,
or outcomes.

## Durable context and ASK

Initial completion creates `CaseStateVersion` and `RagContext` in the same
transaction as the assistant message and run finalization. ASK loads the
thread's current version and its matching `RagContext`; it does not infer
grounding from the latest assistant prose or an opaque context ID alone.

The assistant metadata records `analysis_kind` and action audit information,
but metadata is not the source of truth for ASK grounding.

## Explicit case-information mutation

For an answered thread, `action="add_case_info"` is an explicit mutation
authorization; no intent classifier is used. The worker sends only the current
Case State snapshot and the new user message to
`backend/app/services/chat/case_state_mutation.py`. The model returns a narrow
validated delta (`no_change`, `add`, or `modify`), never a regenerated full
state. Backend code applies the delta to a defensive copy, validates the
complete merged snapshot, and rejects unsupported IDs, stale correction
targets, invalid provenance, or structurally invalid results.

For a non-empty delta, the final transaction creates an immutable child
`CaseStateVersion` with `parent_version_id`, `trigger_message_id`,
`delta_json`, and the complete merged `state_json`; it then persists a fresh
`RagContext`, updates the current-version pointer, writes the grounded
`case_overview`, and completes the run. The parent version and its RAG context
remain unchanged. A `no_change` delta creates no child version and does not
invoke RAG or Main Case Analysis. If the current pointer no longer matches the
captured parent, the run fails as stale and the transaction rolls back.

## Failure behavior

- Missing/invalid extraction fails closed before RAG and Main Case Analysis.
- Missing retrieval context ID or empty retrieval context fails initial durable
  completion validation.
- A Main Case Analysis provider failure fails the run; it must not mutate the
  Case State or create a partial durable context.
- A post-answer ASK failure leaves the existing Case State version untouched.
