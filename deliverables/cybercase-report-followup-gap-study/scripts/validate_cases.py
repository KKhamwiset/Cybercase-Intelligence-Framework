"""Validate CyberCase evaluation JSON files against schema and semantic invariants."""

from __future__ import annotations

import argparse
import copy
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "cybercase_eval_case.schema.json"
)
EXAMPLES_PATH = Path(__file__).resolve().parents[1] / "examples"
INJECTION_MARKERS = ("clarification answer:", "controlled answer:")


def _json_path(parts: Iterable[Any]) -> str:
    value = "$"
    for part in parts:
        value += f"[{part}]" if isinstance(part, int) else f".{part}"
    return value


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    return {value for value in values if value in seen or seen.add(value)}


def _state_map(claim: dict[str, Any]) -> tuple[dict[str, str], set[str]]:
    states: dict[str, str] = {}
    duplicates: set[str] = set()
    for item in claim.get("expected_states", []):
        variant = item.get("variant")
        if not isinstance(variant, str):
            continue
        if variant in states:
            duplicates.add(variant)
        states[variant] = item.get("state")
    return states, duplicates


def schema_errors(document: Any, schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def leaf_errors(error: Any) -> Iterable[Any]:
        if error.context:
            for child in error.context:
                yield from leaf_errors(child)
        else:
            yield error

    leaves = [
        leaf
        for error in validator.iter_errors(document)
        for leaf in leaf_errors(error)
    ]
    messages = {
        f"{_json_path(error.absolute_path)}: schema: {error.message}"
        for error in leaves
    }
    return sorted(messages)


def semantic_errors(document: Any) -> list[str]:
    """Return cross-field errors that JSON Schema cannot express."""

    errors: list[str] = []
    if not isinstance(document, dict):
        return ["$: semantic: document must be an object"]

    source_text = document.get("source_text")
    if not isinstance(source_text, str):
        source_text = ""

    spans = document.get("evidence_spans")
    spans = spans if isinstance(spans, list) else []
    span_ids = [
        span.get("span_id")
        for span in spans
        if isinstance(span, dict) and isinstance(span.get("span_id"), str)
    ]
    for duplicate in sorted(_duplicates(span_ids)):
        errors.append(f"$.evidence_spans: semantic: duplicate span_id {duplicate!r}")
    span_map = {
        span["span_id"]: span
        for span in spans
        if isinstance(span, dict) and isinstance(span.get("span_id"), str)
    }

    for index, span in enumerate(spans):
        if not isinstance(span, dict):
            continue
        start, end, quoted = (
            span.get("char_start"),
            span.get("char_end"),
            span.get("text"),
        )
        prefix = f"$.evidence_spans[{index}]"
        if not isinstance(start, int) or isinstance(start, bool):
            continue
        if not isinstance(end, int) or isinstance(end, bool):
            continue
        if start < 0:
            errors.append(f"{prefix}.char_start: semantic: offset must be nonnegative")
        if end <= start:
            errors.append(
                f"{prefix}: semantic: offsets must be ordered with char_end > char_start"
            )
            continue
        if end > len(source_text):
            errors.append(
                f"{prefix}.char_end: semantic: offset {end} exceeds source length "
                f"{len(source_text)}"
            )
            continue
        if isinstance(quoted, str) and source_text[start:end] != quoted:
            errors.append(
                f"{prefix}.text: semantic: quoted text does not match "
                "source_text at declared offsets"
            )

    claims = document.get("report_claims")
    claims = claims if isinstance(claims, list) else []
    claim_ids = [
        claim.get("claim_id")
        for claim in claims
        if isinstance(claim, dict) and isinstance(claim.get("claim_id"), str)
    ]
    for duplicate in sorted(_duplicates(claim_ids)):
        errors.append(f"$.report_claims: semantic: duplicate claim_id {duplicate!r}")
    claim_map = {
        claim["claim_id"]: claim
        for claim in claims
        if isinstance(claim, dict) and isinstance(claim.get("claim_id"), str)
    }

    timeline = document.get("timeline_gold")
    timeline = timeline if isinstance(timeline, list) else []
    event_ids = [
        event.get("event_id")
        for event in timeline
        if isinstance(event, dict) and isinstance(event.get("event_id"), str)
    ]
    for duplicate in sorted(_duplicates(event_ids)):
        errors.append(f"$.timeline_gold: semantic: duplicate event_id {duplicate!r}")

    mappings = document.get("attck_gold")
    mappings = mappings if isinstance(mappings, list) else []
    technique_ids = [
        mapping.get("technique_id")
        for mapping in mappings
        if isinstance(mapping, dict) and isinstance(mapping.get("technique_id"), str)
    ]
    for duplicate in sorted(_duplicates(technique_ids)):
        errors.append(f"$.attck_gold: semantic: duplicate technique_id {duplicate!r}")
    technique_set = set(technique_ids)
    technique_map = {
        mapping["technique_id"]: mapping
        for mapping in mappings
        if isinstance(mapping, dict)
        and isinstance(mapping.get("technique_id"), str)
    }

    controlled = document.get("controlled_answer")
    answer_ids: set[str] = set()
    if isinstance(controlled, dict) and isinstance(controlled.get("answer_id"), str):
        answer_ids.add(controlled["answer_id"])

    def check_refs(
        values: Any,
        allowed: set[str],
        path: str,
        ref_name: str,
    ) -> None:
        if not isinstance(values, list):
            return
        for index, value in enumerate(values):
            if isinstance(value, str) and value not in allowed:
                errors.append(
                    f"{path}[{index}]: semantic: dangling {ref_name} {value!r}"
                )

    variants = document.get("variants")
    variants = variants if isinstance(variants, dict) else {}
    for variant_name, variant in variants.items():
        if not isinstance(variant, dict):
            continue
        check_refs(
            variant.get("visible_span_ids"),
            set(span_map),
            f"$.variants.{variant_name}.visible_span_ids",
            "span reference",
        )
        if "injected_answer" in variant:
            errors.append(
                f"$.variants.{variant_name}.injected_answer: semantic: answer "
                "injection is forbidden in input variants"
            )
        input_text = variant.get("input_text")
        if isinstance(input_text, str):
            lowered = input_text.casefold()
            for marker in INJECTION_MARKERS:
                if marker in lowered:
                    errors.append(
                        f"$.variants.{variant_name}.input_text: semantic: "
                        f"answer-injection marker {marker!r} is forbidden"
                    )

    target = document.get("decision_target")
    target = target if isinstance(target, dict) else {}
    check_refs(
        target.get("affected_claim_ids"),
        set(claim_map),
        "$.decision_target.affected_claim_ids",
        "claim reference",
    )
    check_refs(
        target.get("affected_attck_ids"),
        technique_set,
        "$.decision_target.affected_attck_ids",
        "ATT&CK reference",
    )
    check_refs(
        target.get("withheld_span_ids"),
        set(span_map),
        "$.decision_target.withheld_span_ids",
        "span reference",
    )
    check_refs(
        target.get("unknown_span_ids"),
        set(span_map),
        "$.decision_target.unknown_span_ids",
        "span reference",
    )

    if isinstance(controlled, dict):
        check_refs(
            controlled.get("source_span_ids"),
            set(span_map),
            "$.controlled_answer.source_span_ids",
            "span reference",
        )

    for index, event in enumerate(timeline):
        if not isinstance(event, dict):
            continue
        check_refs(
            event.get("source_span_ids"),
            set(span_map),
            f"$.timeline_gold[{index}].source_span_ids",
            "span reference",
        )
        check_refs(
            event.get("answer_ids"),
            answer_ids,
            f"$.timeline_gold[{index}].answer_ids",
            "answer reference",
        )

    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, dict):
            continue
        check_refs(
            mapping.get("source_span_ids"),
            set(span_map),
            f"$.attck_gold[{index}].source_span_ids",
            "span reference",
        )
        check_refs(
            mapping.get("answer_ids"),
            answer_ids,
            f"$.attck_gold[{index}].answer_ids",
            "answer reference",
        )

    kind = document.get("case_kind")
    required_variants = {
        "eligible_masked": {"complete", "masked", "clarified"},
        "sufficient": {"sufficient"},
        "explicitly_unknown": {"explicitly_unknown"},
    }.get(kind, set())
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            continue
        prefix = f"$.report_claims[{index}]"
        check_refs(
            claim.get("source_span_ids"),
            set(span_map),
            f"{prefix}.source_span_ids",
            "span reference",
        )
        check_refs(
            claim.get("answer_ids"),
            answer_ids,
            f"{prefix}.answer_ids",
            "answer reference",
        )
        check_refs(
            claim.get("attck_technique_ids"),
            technique_set,
            f"{prefix}.attck_technique_ids",
            "ATT&CK reference",
        )
        states, duplicate_states = _state_map(claim)
        for duplicate in sorted(duplicate_states):
            errors.append(
                f"{prefix}.expected_states: semantic: duplicate variant "
                f"{duplicate!r}"
            )
        missing_states = required_variants - set(states)
        if missing_states:
            errors.append(
                f"{prefix}.expected_states: semantic: missing expected states "
                f"for {sorted(missing_states)!r}"
            )

    expected_gate = document.get("expected_gate")
    expected_gate = expected_gate if isinstance(expected_gate, dict) else {}
    target_slot = target.get("target_slot_id")
    gate_slot = expected_gate.get("target_slot_id")
    affected_claims = set(target.get("affected_claim_ids") or [])
    withheld = set(target.get("withheld_span_ids") or [])
    unknown = set(target.get("unknown_span_ids") or [])

    if kind == "eligible_masked":
        complete = variants.get("complete")
        masked = variants.get("masked")
        complete_visible = (
            set(complete.get("visible_span_ids") or [])
            if isinstance(complete, dict)
            else set()
        )
        masked_visible = (
            set(masked.get("visible_span_ids") or [])
            if isinstance(masked, dict)
            else set()
        )
        if not withheld:
            errors.append(
                "$.decision_target.withheld_span_ids: semantic: eligible case "
                "must withhold at least one span"
            )
        if not withheld <= complete_visible:
            errors.append(
                "$.variants.complete.visible_span_ids: semantic: complete input "
                "must expose every withheld span"
            )
        leaked_visible = withheld & masked_visible
        if leaked_visible:
            errors.append(
                "$.variants.masked.visible_span_ids: semantic: withheld spans "
                f"remain visible {sorted(leaked_visible)!r}"
            )
        if isinstance(masked, dict):
            masked_text = str(masked.get("input_text") or "").casefold()
            for span_id in withheld:
                span_text = str(span_map.get(span_id, {}).get("text") or "")
                if span_text and span_text.casefold() in masked_text:
                    errors.append(
                        "$.variants.masked.input_text: semantic: withheld span "
                        f"{span_id!r} leaks into masked input"
                    )
            if isinstance(controlled, dict):
                answer_text = str(controlled.get("text") or "")
                if answer_text and answer_text.casefold() in masked_text:
                    errors.append(
                        "$.variants.masked.input_text: semantic: canonical "
                        "controlled answer leaks into masked input"
                    )
        if not isinstance(controlled, dict):
            errors.append(
                "$.controlled_answer: semantic: eligible case requires one "
                "canonical controlled answer"
            )
        else:
            if controlled.get("target_slot_id") != target_slot:
                errors.append(
                    "$.controlled_answer.target_slot_id: semantic: must match "
                    "$.decision_target.target_slot_id"
                )
            if controlled.get("provenance_type") in {
                "source_span",
                "analyst_adjudicated",
            } and not set(controlled.get("source_span_ids") or []) <= withheld:
                errors.append(
                    "$.controlled_answer.source_span_ids: semantic: benchmark "
                    "answer lineage must resolve to withheld source spans"
                )
        if expected_gate.get("action") != "ask":
            errors.append(
                "$.expected_gate.action: semantic: eligible case must expect ask"
            )
        if gate_slot != target_slot:
            errors.append(
                "$.expected_gate.target_slot_id: semantic: must match "
                "$.decision_target.target_slot_id"
            )
        canonical_id = controlled.get("answer_id") if isinstance(controlled, dict) else None
        for claim_id, claim in claim_map.items():
            states, _ = _state_map(claim)
            claim_answers = set(claim.get("answer_ids") or [])
            if claim_id in affected_claims:
                if canonical_id not in claim_answers:
                    errors.append(
                        f"$.report_claims[{claim_id}].answer_ids: semantic: "
                        "affected claim must link the canonical answer"
                    )
                if states.get("complete") != "retain_supported":
                    errors.append(
                        f"$.report_claims[{claim_id}].expected_states: semantic: "
                        "affected complete claim must be retain_supported"
                    )
                if states.get("masked") not in {"omit", "qualify", "abstain"}:
                    errors.append(
                        f"$.report_claims[{claim_id}].expected_states: semantic: "
                        "affected masked claim must omit, qualify, or abstain"
                    )
                if states.get("clarified") != "add_supported":
                    errors.append(
                        f"$.report_claims[{claim_id}].expected_states: semantic: "
                        "affected clarified claim must be add_supported"
                    )
            else:
                if claim_answers:
                    errors.append(
                        f"$.report_claims[{claim_id}].answer_ids: semantic: "
                        "unaffected claim must not depend on the controlled answer"
                    )
                if any(
                    states.get(variant) != "retain_supported"
                    for variant in ("complete", "masked", "clarified")
                ):
                    errors.append(
                        f"$.report_claims[{claim_id}].expected_states: semantic: "
                        "unaffected claims must retain_supported in every variant"
                    )

    elif kind == "sufficient":
        if controlled is not None:
            errors.append(
                "$.controlled_answer: semantic: sufficient control forbids an answer"
            )
        if expected_gate.get("action") != "proceed" or expected_gate.get("question") is not None:
            errors.append(
                "$.expected_gate: semantic: sufficient control must proceed "
                "without a question"
            )
        if affected_claims or withheld or unknown or target_slot is not None:
            errors.append(
                "$.decision_target: semantic: sufficient control cannot declare "
                "a gap, target slot, or affected claim"
            )
        for claim_id, claim in claim_map.items():
            states, _ = _state_map(claim)
            if states.get("sufficient") != "retain_supported":
                errors.append(
                    f"$.report_claims[{claim_id}].expected_states: semantic: "
                    "sufficient claims must retain_supported"
                )

    elif kind == "explicitly_unknown":
        if controlled is not None:
            errors.append(
                "$.controlled_answer: semantic: explicitly-unknown control "
                "forbids an answer"
            )
        if expected_gate.get("action") != "proceed" or expected_gate.get("question") is not None:
            errors.append(
                "$.expected_gate: semantic: explicitly-unknown control must "
                "proceed without a question"
            )
        if gate_slot != target_slot:
            errors.append(
                "$.expected_gate.target_slot_id: semantic: must match "
                "$.decision_target.target_slot_id"
            )
        visible = variants.get("explicitly_unknown")
        visible_ids = (
            set(visible.get("visible_span_ids") or [])
            if isinstance(visible, dict)
            else set()
        )
        if not unknown or not unknown <= visible_ids:
            errors.append(
                "$.decision_target.unknown_span_ids: semantic: explicit "
                "unavailability spans must be present and visible"
            )
        for claim_id, claim in claim_map.items():
            states, _ = _state_map(claim)
            if claim_id in affected_claims:
                if states.get("explicitly_unknown") not in {"qualify", "abstain"}:
                    errors.append(
                        f"$.report_claims[{claim_id}].expected_states: semantic: "
                        "affected explicitly-unknown claim must qualify or abstain"
                    )
            elif states.get("explicitly_unknown") != "retain_supported":
                errors.append(
                    f"$.report_claims[{claim_id}].expected_states: semantic: "
                    "unaffected explicitly-unknown claim must be retain_supported"
                )
        affected_attck_ids = target.get("affected_attck_ids")
        if isinstance(affected_attck_ids, list):
            for index, technique_id in enumerate(affected_attck_ids):
                mapping = technique_map.get(technique_id)
                if mapping is not None and mapping.get("applicability") != "excluded":
                    errors.append(
                        f"$.decision_target.affected_attck_ids[{index}]: semantic: "
                        f"affected ATT&CK mapping {technique_id!r} must have "
                        "applicability 'excluded'"
                    )

    return errors


def validate_document(document: Any, schema: dict[str, Any]) -> list[str]:
    """Validate one already-loaded document; useful for tests and mutation checks."""

    return schema_errors(document, schema) + semantic_errors(document)


def _expand_paths(arguments: list[str]) -> list[Path]:
    paths: list[Path] = []
    for argument in arguments:
        matches = [Path(match) for match in glob.glob(argument)]
        paths.extend(matches or [Path(argument)])
    return paths


def _set_claim_state(
    document: dict[str, Any], claim_id: str, variant: str, state: str
) -> None:
    for claim in document["report_claims"]:
        if claim["claim_id"] != claim_id:
            continue
        for expected_state in claim["expected_states"]:
            if expected_state["variant"] == variant:
                expected_state["state"] = state
                return
    raise ValueError(f"fixture does not contain {claim_id!r}/{variant!r}")


def run_self_test(schema: dict[str, Any]) -> int:
    """Run permanent valid-fixture and negative-mutation checks."""

    fixture_paths = {
        "eligible_masked": EXAMPLES_PATH / "cybercase_eval_case.example.json",
        "sufficient": EXAMPLES_PATH / "cybercase_eval_case.sufficient.example.json",
        "explicitly_unknown": (
            EXAMPLES_PATH / "cybercase_eval_case.explicitly_unknown.example.json"
        ),
    }
    try:
        fixtures = {
            name: json.loads(path.read_text(encoding="utf-8"))
            for name, path in fixture_paths.items()
        }
    except Exception as exc:
        print(f"self-test: FAIL: could not load fixture: {exc}", file=sys.stderr)
        return 1

    failures = 0
    for name, fixture in fixtures.items():
        errors = validate_document(fixture, schema)
        if errors:
            failures += 1
            print(
                f"self-test valid {name}: FAIL ({len(errors)} error(s))",
                file=sys.stderr,
            )
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
        else:
            print(f"self-test valid {name}: PASS")

    eligible = fixtures["eligible_masked"]
    sufficient = fixtures["sufficient"]
    unknown = fixtures["explicitly_unknown"]
    mutations: list[tuple[str, dict[str, Any], str]] = []

    mutated = copy.deepcopy(eligible)
    _set_claim_state(mutated, "C-002", "complete", "omit")
    mutations.append(
        ("eligible_affected_complete_not_retained", mutated, "affected complete claim")
    )

    mutated = copy.deepcopy(unknown)
    _set_claim_state(mutated, "C-001", "explicitly_unknown", "qualify")
    mutations.append(
        (
            "unknown_unaffected_claim_not_retained",
            mutated,
            "unaffected explicitly-unknown claim",
        )
    )

    mutated = copy.deepcopy(unknown)
    mutated["attck_gold"][0]["applicability"] = "required"
    mutations.append(
        ("unknown_affected_attck_not_excluded", mutated, "must have applicability")
    )

    mutated = copy.deepcopy(eligible)
    mutated["evidence_spans"][1]["span_id"] = mutated["evidence_spans"][0]["span_id"]
    mutations.append(("duplicate_id", mutated, "duplicate span_id"))

    mutated = copy.deepcopy(eligible)
    mutated["report_claims"][0]["source_span_ids"] = ["SPAN-MISSING"]
    mutations.append(("dangling_reference", mutated, "dangling span reference"))

    mutated = copy.deepcopy(eligible)
    mutated["evidence_spans"][0]["char_start"] = 8
    mutated["evidence_spans"][0]["char_end"] = 3
    mutations.append(("bad_offsets", mutated, "offsets must be ordered"))

    mutated = copy.deepcopy(eligible)
    mutated["variants"]["masked"]["input_text"] += " Controlled answer: forbidden."
    mutations.append(("input_injection", mutated, "answer-injection marker"))

    mutated = copy.deepcopy(sufficient)
    mutated["controlled_answer"] = copy.deepcopy(eligible["controlled_answer"])
    mutations.append(("illegal_control_answer", mutated, "forbids an answer"))

    mutated = copy.deepcopy(unknown)
    mutated["expected_gate"]["question"] = "Which script executed?"
    mutations.append(("illegal_control_question", mutated, "without a question"))

    for name, mutated, expected_fragment in mutations:
        errors = validate_document(mutated, schema)
        if not errors:
            failures += 1
            print(f"self-test mutation {name}: FAIL (accepted)", file=sys.stderr)
        elif not any(expected_fragment in error for error in errors):
            failures += 1
            print(
                f"self-test mutation {name}: FAIL (expected error containing "
                f"{expected_fragment!r})",
                file=sys.stderr,
            )
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
        else:
            print(f"self-test mutation {name}: PASS (rejected)")

    if failures:
        print(f"Self-test failed: {failures} check(s).", file=sys.stderr)
        return 1
    print(
        f"Self-test passed: {len(fixtures)} valid fixtures accepted; "
        f"{len(mutations)} invalid mutations rejected."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run built-in valid-fixture and negative-mutation checks",
    )
    parser.add_argument("json_paths", nargs="*", help="JSON path(s); globs are accepted")
    args = parser.parse_args(argv)

    if args.self_test and args.json_paths:
        parser.error("--self-test cannot be combined with JSON paths")
    if not args.self_test and not args.json_paths:
        parser.error("provide JSON path(s) or --self-test")

    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        print(f"{SCHEMA_PATH}: ERROR: schema could not be loaded: {exc}", file=sys.stderr)
        return 2

    if args.self_test:
        return run_self_test(schema)

    paths = _expand_paths(args.json_paths)
    failures = 0
    seen_case_ids: dict[str, Path] = {}
    split_assignments: dict[str, set[str]] = defaultdict(set)
    inference_splits: dict[str, set[tuple[str, str]]] = defaultdict(set)

    for path in paths:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"{path}: ERROR: could not load JSON: {exc}", file=sys.stderr)
            failures += 1
            continue

        errors = validate_document(document, schema)
        case_id = document.get("case_id") if isinstance(document, dict) else None
        if isinstance(case_id, str):
            if case_id in seen_case_ids:
                errors.append(
                    f"$.case_id: semantic: duplicate case_id also used by "
                    f"{seen_case_ids[case_id]}"
                )
            else:
                seen_case_ids[case_id] = path
        split_group = document.get("split_group") if isinstance(document, dict) else None
        inference_group = (
            document.get("inference_group") if isinstance(document, dict) else None
        )
        split = document.get("split") if isinstance(document, dict) else None
        if isinstance(split_group, str) and isinstance(split, str):
            split_assignments[split_group].add(split)
        if (
            isinstance(inference_group, str)
            and isinstance(split_group, str)
            and isinstance(split, str)
        ):
            inference_splits[inference_group].add((split_group, split))

        if errors:
            failures += 1
            print(f"{path}: FAIL ({len(errors)} error(s))", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
        else:
            print(f"{path}: OK")

    for group, splits in split_assignments.items():
        if len(splits) > 1:
            failures += 1
            print(
                f"cross-file: FAIL: split_group {group!r} appears in multiple "
                f"splits {sorted(splits)!r}",
                file=sys.stderr,
            )
    for group, assignments in inference_splits.items():
        if len(assignments) > 1:
            failures += 1
            print(
                f"cross-file: FAIL: inference_group {group!r} maps to multiple "
                f"split assignments {sorted(assignments)!r}",
                file=sys.stderr,
            )

    if failures:
        print(f"Validation failed: {failures} file/group failure(s).", file=sys.stderr)
        return 1
    print(f"Validated {len(paths)} case file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
