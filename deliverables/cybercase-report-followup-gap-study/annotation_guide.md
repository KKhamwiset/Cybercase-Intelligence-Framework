# Annotation Guide

Version 2.0, prospective. This guide creates gold for B0-external-adapted/B1; it does not modify or annotate the exact NFI B0-reproduction schema.

## Roles and independence

Two cybersecurity-competent annotators independently prepare/score cases; a third adjudicates. Gold is created before model output. Preserve source licenses, avoid real-person data in public artifacts, and never use system output as evidence.

## Definitions

- **Report-critical fact:** an incident-specific fact whose value can change a required claim, timeline event, or exact ATT&CK mapping.
- **Target slot:** the one fixed report/ATT&CK field identified by `target_slot_id`.
- **Eligible gap:** an absent, answerable report-critical fact represented by withheld source spans.
- **Explicitly unknown:** the source states the material fact is unavailable; asking again cannot retrieve an answer.
- **Canonical answer:** the sole gold answer for an eligible case, with one `answer_id`, target slot, provenance, and source IDs when available. It is not embedded in an input variant.
- **Evidence lineage:** resolvable source-span and/or answer IDs attached to claims/events/mappings. It enables audit but does not establish truth by itself.
- **Atomic question:** one question requesting one topic/answer slot. A single question mark is not sufficient proof of semantic atomicity.

## Common case setup

1. Freeze dataset URL/version/license/hash, source unit, ATT&CK commit, and immutable `source_text`.
2. Assign unique `case_id`. Assign both `split_group` and `inference_group`; for CAM-LDS, the scenario family is the inference unit and must not cross development/test.
3. Copy minimal exact evidence spans with stable IDs, source references, and half-open offsets `[char_start, char_end)`. Verify `source_text[start:end] == text`.
4. Adjudicate atomic report claims, timeline events, and exact ATT&CK mappings. Every reference must resolve.
5. Record per-variant claim expectations. Use `retain_supported` for unaffected claims; never force them to disappear merely because another fact was masked.

## Case-kind decision

### eligible_masked

Use only when both annotators agree that one fact:

- is absent from the masked input and not inferable without assumption;
- is incident-specific rather than general ATT&CK knowledge;
- can change at least one named required claim or exact mapping;
- can be answered in one topic from a known source or controlled operational answer; and
- can be removed without creating contradictory or nonsensical text.

Create `complete` and `masked` inputs. Complete exposes every withheld span; masked exposes none and contains neither the withheld span text nor canonical answer. Record one target slot, affected claim IDs, affected ATT&CK IDs, expected `ask`, one gold question, and one canonical answer.

For affected claims, complete state must be `retain_supported`, masked state must be `omit`, `qualify`, or `abstain`, and clarified state must be `add_supported` and link the canonical `answer_id`. Unaffected claims must be `retain_supported` in complete, masked, and clarified states and must not link the answer.

### sufficient

Use when the visible source already supports every required decision. Provide only the `sufficient` input. Set resolution to `already_sufficient`, target slot to null, expected action to `proceed`, and question/controlled answer to null. All claims use `retain_supported`.

### explicitly_unknown

Use when a visible source span explicitly records that a material fact is unavailable or unknown. Provide only the `explicitly_unknown` input, identify its target slot/affected claims, link `unknown_span_ids`, expect `proceed`, and provide no question or answer. Affected claims must `qualify` or `abstain`; unaffected claims must `retain_supported`. Every affected ATT&CK ID must resolve to an `attck_gold` mapping marked `excluded`, and emitting that mapping is an error.

## Gold question

The eligible gold question must be one line, at most 300 characters, end in one question mark, request one target slot, avoid presupposing the answer, and avoid asking the person for ATT&CK/general knowledge. Semantically equivalent wording is accepted by adjudication; exact string matching is not required.

The research implementation must measure compoundness manually. The current CyberCase prompt asks for one fact, while runtime validation only rejects empty, over-length, multiline, or multiple-question-mark output; it does not detect “Which script ran and which account launched it?” as two topics when written with one question mark.

## Canonical answer and provenance

- `source_span`: answer is copied/paraphrased from withheld evidence; retain its source IDs and set `user_reported: false`.
- `analyst_adjudicated`: experts derive the controlled answer under a documented rule; retain supporting source IDs and set `user_reported: false`.
- `user_reported`: an operational person actually supplies the assertion; set `user_reported: true`. Empty source-span IDs are allowed, and downstream text must preserve reported/uncertain status.

The answer ID and target slot must match the decision target. Supply the answer exactly once only after B1 asks a valid eligible question; it must never be embedded in an input variant. Sufficient and explicitly-unknown controls never receive an answer.

## Claim, timeline, and ATT&CK gold

### Claims

Decompose output into independently verifiable propositions. During scoring use:

- `correct_supported`: proposition correct and cited lineage sufficient;
- `correct_unlineaged`: correct-sounding but lineage absent/invalid (counts as ungrounded false positive for supported-claim F1);
- `incorrect` or `unsupported`;
- `missing`; or
- `proper_abstention` where the expected state is qualify/abstain.

Exact normalized matches are accepted first. Otherwise two blinded adjudicators must accept semantic equivalence, with a third resolving disagreement. Enforce one-to-one predicted-to-gold matching.

### Timeline

Record one event ID per event, normalized time or supported interval, timezone/uncertainty, description, required status, and source/answer lineage. Do not invent precision. A correct event with fabricated exact time is not fully correct.

### ATT&CK

Use exact IDs from the frozen STIX snapshot. Record name, tactic, applicability (`required`, `acceptable`, or `excluded`), and lineage. Tool presence or contextual plausibility is insufficient. If evidence cannot distinguish a sub-technique, require abstention or only the supported parent.

## Gate and resolution labels

- Eligible: correct behavior is exactly one necessary, answerable question for the gold slot.
- Sufficient: correct behavior is proceed/no question.
- Explicitly unknown: correct behavior is proceed/no question and qualify/abstain.
- More than one, compound, wrong-slot, leading, unnecessary, or unanswerable questions are failures.
- Resolution succeeds only if the correct eligible question leads to the one canonical answer, provenance is preserved, and the answer is available to final synthesis exactly once.

## Adjudication and quality control

1. Annotators work independently and record rationales.
2. Run [scripts/validate_cases.py](scripts/validate_cases.py) before any model access.
3. Compare case kind, gap necessity, target slot, expected question, claim states, timeline, and ATT&CK gold.
4. The adjudicator reads source evidence and both rationales, never system output.
5. Report agreement and adjudication rate. Version corrections; post-unblinding changes require an erratum and sensitivity analysis.

## Fictitious examples

### Eligible

Complete evidence states that `wscript.exe` launched `invoice_update.js`; masked evidence omits only that sentence. The execution claim and T1059.007 depend on it.

- Acceptable: “What process or script, if any, executed after the archive was received?”
- Canonical answer: “The workstation launched invoice_update.js with wscript.exe at 09:14 UTC.”
- Provenance: source span, not user-reported.

### Compound failure

“Which user opened the archive, what script ran, and was data exfiltrated?” requests three slots. Mark compound and over budget.

### General-knowledge failure

“Which ATT&CK ID represents JavaScript execution?” asks the user for ontology knowledge. The system must consult the frozen ontology.

### Sufficient control

Evidence already states the process, command, host, and timestamp. Proceed without asking; confirmation is unnecessary.

### Explicitly-unknown control

Evidence states that investigators could not determine whether a script executed. Proceed, preserve uncertainty, and abstain from an exact execution mapping. Asking which script ran is redundant and unanswerable.

### User-reported operational answer

If a person says “I think I entered my password,” tag the answer `user_reported`; a report may state that the person reported possible credential entry, but not that credential capture was verified.
