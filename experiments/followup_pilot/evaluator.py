"""Blind, interactive manual evaluator for two pilot result files."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from .runner import OUTSIDE_ANSWER_SHEET, load_case
from .schemas import (
    EvaluationResult,
    ExperimentResult,
    FieldRating,
    PilotCase,
    RECOVERABLE_HIDDEN_FIELDS,
    SystemEvaluation,
    SystemMetrics,
)


LABELS = ("System A", "System B")
VALID_METHOD_PAIRS = (
    frozenset({"no_followup", "adaptive_followup"}),
    frozenset({"no_followup", "post_rag_adaptive"}),
    frozenset({"post_rag_adaptive", "pre_rag_adaptive"}),
)
RATINGS: tuple[FieldRating, ...] = (
    "correct_supported",
    "missing",
    "incorrect",
    "unsupported",
)
InputCallable = Callable[[str], str]
OutputCallable = Callable[[str], None]


class ShuffleLike(Protocol):
    def shuffle(self, values: list[ExperimentResult]) -> None: ...


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_result(path: Path) -> ExperimentResult:
    return ExperimentResult.model_validate_json(path.read_text(encoding="utf-8"))


def exact_duplicate_question_count(result: ExperimentResult) -> int:
    counts = Counter(item.question for item in result.questions)
    return sum(count - 1 for count in counts.values())


def recovered_hidden_fields(result: ExperimentResult) -> set[str]:
    recovered: set[str] = set()
    for question in result.questions:
        answer = question.answer.strip()
        if not answer or answer == OUTSIDE_ANSWER_SHEET:
            continue
        recovered.update(question.requested_fields)
    return recovered.intersection(RECOVERABLE_HIDDEN_FIELDS)


def calculate_metrics(
    *,
    case: PilotCase,
    result: ExperimentResult,
    field_scores: dict[str, FieldRating],
) -> SystemMetrics:
    total_fields = len(case.reference_fields)
    correct = sum(score == "correct_supported" for score in field_scores.values())
    recovered = recovered_hidden_fields(result)
    utilized = {
        field
        for field in recovered
        if field_scores.get(field) == "correct_supported"
    }
    hidden_total = len(RECOVERABLE_HIDDEN_FIELDS)
    return SystemMetrics(
        analysis_completeness=correct / total_fields if total_fields else 0.0,
        hidden_field_recovery=len(recovered) / hidden_total,
        final_hidden_field_utilization=len(utilized) / hidden_total,
        questions_asked=len(result.questions),
        exact_duplicate_question_count=exact_duplicate_question_count(result),
        compound_question_count=sum(item.is_compound for item in result.questions),
        unsupported_field_count=sum(
            score == "unsupported" for score in field_scores.values()
        ),
    )


def _prompt_rating(
    *,
    system_label: str,
    field: str,
    input_fn: InputCallable,
    output_fn: OutputCallable,
) -> FieldRating:
    while True:
        value = input_fn(
            f"{system_label} — {field} "
            "[correct_supported/missing/incorrect/unsupported]: "
        ).strip()
        if value in RATINGS:
            return value  # type: ignore[return-value]
        output_fn("กรุณาเลือกหนึ่งป้ายกำกับจากรายการที่กำหนด")


def conduct_blind_evaluation(
    *,
    case: PilotCase,
    results: Sequence[ExperimentResult],
    input_fn: InputCallable = input,
    output_fn: OutputCallable = print,
    rng: ShuffleLike | None = None,
) -> EvaluationResult:
    if len(results) != 2:
        raise ValueError("the blind evaluator requires exactly two result files")
    if frozenset(result.method for result in results) not in VALID_METHOD_PAIRS:
        raise ValueError(
            "results must contain one supported pair of pilot methods"
        )
    if any(result.case_id != case.case_id for result in results):
        raise ValueError("both results must match the selected case")

    started_at = utc_now()
    shuffled = list(results)
    (rng or random.SystemRandom()).shuffle(shuffled)
    assignment = dict(zip(LABELS, shuffled, strict=True))

    output_fn("Blind evaluation: method mapping remains hidden until scoring ends.")
    output_fn("Reference checklist (ใช้กับทั้งสองระบบ):")
    for field, expected in case.reference_fields.items():
        output_fn(f"- {field}: {expected}")
    for label in LABELS:
        output_fn(f"\n{label} — Final analysis")
        output_fn(assignment[label].final_analysis)

    collected_scores: dict[str, dict[str, FieldRating]] = {}
    for label in LABELS:
        scores: dict[str, FieldRating] = {}
        for field in case.reference_fields:
            scores[field] = _prompt_rating(
                system_label=label,
                field=field,
                input_fn=input_fn,
                output_fn=output_fn,
            )
        collected_scores[label] = scores

    systems = {
        label: SystemEvaluation(
            experiment_id=assignment[label].experiment_id,
            field_scores=collected_scores[label],
            metrics=calculate_metrics(
                case=case,
                result=assignment[label],
                field_scores=collected_scores[label],
            ),
        )
        for label in LABELS
    }
    mapping = {label: assignment[label].method for label in LABELS}
    evaluation = EvaluationResult(
        evaluation_id=str(uuid4()),
        case_id=case.case_id,
        systems=systems,
        mapping=mapping,
        started_at=started_at,
        finished_at=utc_now(),
    )

    output_fn("\nScoring complete. Method mapping:")
    for label in LABELS:
        output_fn(f"- {label}: {mapping[label]}")
    return evaluation


def save_evaluation(evaluation: EvaluationResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(evaluation.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path, nargs=2)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main() -> None:
    args = build_argument_parser().parse_args()
    case = load_case(args.case)
    results = [load_result(path) for path in args.results]
    evaluation = conduct_blind_evaluation(case=case, results=results)
    saved = save_evaluation(evaluation, args.output)
    print(f"Saved evaluation: {saved}")


if __name__ == "__main__":
    main()


__all__ = [
    "calculate_metrics",
    "conduct_blind_evaluation",
    "exact_duplicate_question_count",
    "load_result",
    "recovered_hidden_fields",
    "save_evaluation",
]

