# Chat Analysis Contract

## Main Case Analysis module

The internal service is `backend/app/services/case_analysis/service.py`.

```python
await request_case_analysis(
    case_state_json=validated_case_state,
    analysis_context=grounding_snapshot,
    question=None | user_question,
)
```

Current contract properties:

- Prompt version: `main_case_analysis_v1`.
- `case_state_json` is the authoritative, validated Case State input.
- `analysis_context` contains already-persisted/retrieved context and MITRE
  rows; the module does not retrieve, extract, classify intent, mutate state,
  or generate a report.
- `question=None` requests a grounded initial analysis. A non-empty question is
  the post-answer ASK path.
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

## Failure behavior

- Missing/invalid extraction fails closed before RAG and Main Case Analysis.
- Missing retrieval context ID or empty retrieval context fails initial durable
  completion validation.
- A Main Case Analysis provider failure fails the run; it must not mutate the
  Case State or create a partial durable context.
- A post-answer ASK failure leaves the existing Case State version untouched.
