from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from app.services.case_analysis import deterministic_value_mismatches

Label = Literal["supported", "contradicted", "unsupported"]
LABELS: tuple[Label, ...] = ("supported", "contradicted", "unsupported")
DEFAULT_DATASET = Path(__file__).with_name("pilot_dataset.json")


def _has_citation(case: dict[str, Any]) -> bool:
    return bool(case.get("source_id") and case.get("exact_quote"))


def _has_unique_valid_span(case: dict[str, Any]) -> bool:
    quote = str(case.get("exact_quote", ""))
    source = str(case.get("source_text", ""))
    first = source.find(quote) if quote else -1
    return first >= 0 and source.find(quote, first + 1) < 0


def predict_b0(case: dict[str, Any]) -> Label:
    """Citation-presence acceptance without span or semantic validation."""

    return "supported" if _has_citation(case) else "unsupported"


def predict_b1(case: dict[str, Any]) -> Label:
    """Deterministic span/value gates followed by a frozen three-way label."""

    if not _has_citation(case) or not _has_unique_valid_span(case):
        return "unsupported"
    if deterministic_value_mismatches(
        str(case["claim_text"]), str(case["exact_quote"])
    ):
        return "unsupported"
    if case.get("source_type") == "retrieved_context":
        return "unsupported"
    semantic_label = case.get("semantic_label")
    if semantic_label == "entailed":
        return "supported"
    if semantic_label == "contradicted":
        return "contradicted"
    return "unsupported"


def _safe_ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _classification_metrics(
    cases: list[dict[str, Any]], predictions: list[Label]
) -> dict[str, dict[str, float | int]]:
    metrics: dict[str, dict[str, float | int]] = {}
    for label in LABELS:
        true_positive = sum(
            case["oracle_class"] == label and prediction == label
            for case, prediction in zip(cases, predictions, strict=True)
        )
        false_positive = sum(
            case["oracle_class"] != label and prediction == label
            for case, prediction in zip(cases, predictions, strict=True)
        )
        false_negative = sum(
            case["oracle_class"] == label and prediction != label
            for case, prediction in zip(cases, predictions, strict=True)
        )
        precision_raw = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall_raw = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1 = (
            round(2 * precision_raw * recall_raw / (precision_raw + recall_raw), 4)
            if precision_raw + recall_raw
            else 0.0
        )
        metrics[label] = {
            "precision": round(precision_raw, 4),
            "recall": round(recall_raw, 4),
            "f1": f1,
            "support": sum(case["oracle_class"] == label for case in cases),
        }
    return metrics


def _baseline_metrics(
    cases: list[dict[str, Any]], predictions: list[Label]
) -> dict[str, Any]:
    accepted_indexes = [
        index for index, prediction in enumerate(predictions) if prediction == "supported"
    ]
    negative_indexes = [
        index for index, case in enumerate(cases) if case["oracle_class"] != "supported"
    ]
    supported_indexes = [
        index for index, case in enumerate(cases) if case["oracle_class"] == "supported"
    ]
    false_acceptances = sum(
        predictions[index] == "supported" for index in negative_indexes
    )
    retained_supported = sum(
        predictions[index] == "supported" for index in supported_indexes
    )
    accepted_with_valid_spans = sum(
        _has_unique_valid_span(cases[index]) for index in accepted_indexes
    )
    return {
        "prediction_counts": dict(Counter(predictions)),
        "per_class": _classification_metrics(cases, predictions),
        "false_acceptance_rate": _safe_ratio(
            false_acceptances, len(negative_indexes)
        ),
        "valid_citation_coverage": _safe_ratio(
            accepted_with_valid_spans, len(accepted_indexes)
        ),
        "supported_claim_retention": _safe_ratio(
            retained_supported, len(supported_indexes)
        ),
    }


def evaluate_dataset(payload: dict[str, Any]) -> dict[str, Any]:
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("pilot dataset must contain a non-empty cases list")
    for case in cases:
        if case.get("oracle_class") not in LABELS:
            raise ValueError("every pilot case must have a supported oracle class")

    b0_predictions = [predict_b0(case) for case in cases]
    b1_predictions = [predict_b1(case) for case in cases]
    return {
        "dataset_name": payload.get("dataset_name", "unknown"),
        "case_count": len(cases),
        "result_scope": (
            "Synthetic oracle and deterministic wiring validation only; these "
            "numbers are not empirical LLM performance."
        ),
        "baselines": {
            "B0_citation_presence": _baseline_metrics(cases, b0_predictions),
            "B1_deterministic_three_way": _baseline_metrics(cases, b1_predictions),
        },
    }


def run(dataset_path: Path = DEFAULT_DATASET) -> dict[str, Any]:
    return evaluate_dataset(json.loads(dataset_path.read_text(encoding="utf-8")))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.dataset)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
