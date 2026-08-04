"""Terminal runner for the bounded follow-up pilot."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Protocol
from uuid import uuid4


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.schemas.chat.rag import QueryResponse  # noqa: E402
from app.services.chat.followup_policy import (  # noqa: E402
    AnthropicFollowUpPolicy,
    ClarificationExchange,
    FollowUpDecision,
    build_clarified_query,
)
from app.services.chat.rag_client import request_rag  # noqa: E402

from .schemas import (  # noqa: E402
    ExperimentResult,
    HiddenField,
    Method,
    PilotCase,
    QuestionRecord,
    RagCallRecord,
)


MAX_FOLLOWUP_ROUNDS = 3
OUTSIDE_ANSWER_SHEET = "ไม่ทราบและไม่มีข้อมูลดังกล่าวในสำนวนที่มี"
DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results"
RagCallable = Callable[[str], Awaitable[QueryResponse]]
OutputCallable = Callable[[str], None]
InputCallable = Callable[[str], str]


class FollowUpPolicyLike(Protocol):
    async def decide(
        self,
        *,
        original_user_content: str,
        clarification_exchanges: Sequence[ClarificationExchange],
        rag_answer: str,
    ) -> FollowUpDecision: ...


@dataclass(frozen=True)
class HumanAnswer:
    answer: str
    is_compound: bool = False
    requested_fields: tuple[HiddenField, ...] = ()


AnswerProvider = Callable[[PilotCase, int, str], HumanAnswer]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_case(path: Path) -> PilotCase:
    return PilotCase.model_validate_json(path.read_text(encoding="utf-8"))


def build_initial_query(case: PilotCase) -> str:
    """Build the one frozen initial query shared by both conditions."""

    return (
        f"{case.original_request.strip()}\n\n"
        f"ข้อมูลเหตุการณ์ที่มีในสำนวน:\n{case.initial_context.strip()}"
    )


def _normalize_question(question: str) -> str:
    return " ".join(question.split()).casefold()


async def _timed_rag_call(
    *,
    query: str,
    round_number: int,
    rag_call: RagCallable,
) -> tuple[QueryResponse, RagCallRecord]:
    started = perf_counter()
    response = await rag_call(query)
    elapsed_ms = max(0, round((perf_counter() - started) * 1000))
    if not response.answer.strip():
        raise ValueError("RAG service returned a blank analysis")
    return response, RagCallRecord(
        round=round_number,
        query=query,
        retrieval_context_id=response.retrieval_context_id,
        latency_ms=elapsed_ms,
    )


def _interactive_answer_provider(
    *,
    input_fn: InputCallable,
    output_fn: OutputCallable,
) -> AnswerProvider:
    def provide(case: PilotCase, round_number: int, question: str) -> HumanAnswer:
        output_fn(f"\nคำถามรอบที่ {round_number}: {question}")
        output_fn("ตอบโดยใช้เฉพาะข้อเท็จจริงใน answer sheet เท่านั้น")
        output_fn(
            "ถ้าคำถามอยู่นอก answer sheet ให้ตอบ: " + OUTSIDE_ANSWER_SHEET
        )
        answer = input_fn("คำตอบ: ").strip()
        while not answer:
            answer = input_fn("กรุณากรอกคำตอบ: ").strip()

        compound_text = input_fn("คำถามนี้ขอข้อมูลมากกว่าหนึ่งเรื่องหรือไม่ [y/N]: ")
        is_compound = compound_text.strip().casefold() in {"y", "yes"}

        allowed = {"affected_account", "initial_access"}
        while True:
            requested_text = input_fn(
                "ฟิลด์ที่คำถามร้องขอ "
                "[affected_account, initial_access, none; คั่นด้วย comma]: "
            ).strip()
            if not requested_text or requested_text.casefold() == "none":
                requested: tuple[HiddenField, ...] = ()
                break
            values = tuple(
                value.strip() for value in requested_text.split(",") if value.strip()
            )
            if values and set(values).issubset(allowed) and len(values) == len(set(values)):
                requested = tuple(values)  # type: ignore[assignment]
                break
            output_fn("กรุณาเลือกเฉพาะ affected_account, initial_access หรือ none")

        return HumanAnswer(
            answer=answer,
            is_compound=is_compound,
            requested_fields=requested,
        )

    return provide


def print_answer_sheet(case: PilotCase, output_fn: OutputCallable = print) -> None:
    output_fn("\nControlled answer sheet (สำหรับผู้ทดสอบเท่านั้น):")
    for field, answer in case.hidden_answers.items():
        output_fn(f"- {field}: {answer}")
    output_fn(f"- ข้อมูลนอกเหนือจากนี้: {OUTSIDE_ANSWER_SHEET}")


async def run_no_followup(
    case: PilotCase,
    *,
    rag_call: RagCallable = request_rag,
    experiment_id: str | None = None,
    rag_model: str = "existing-rag-service",
    followup_model: str = settings.chat_followup_policy_model,
) -> ExperimentResult:
    started_at = utc_now()
    total_started = perf_counter()
    initial_query = build_initial_query(case)
    response, call_record = await _timed_rag_call(
        query=initial_query,
        round_number=0,
        rag_call=rag_call,
    )
    finished_at = utc_now()
    return ExperimentResult(
        experiment_id=experiment_id or str(uuid4()),
        case_id=case.case_id,
        method="no_followup",
        original_request=case.original_request,
        initial_context=case.initial_context,
        questions=[],
        followup_rounds=0,
        final_rag_query=initial_query,
        final_analysis=response.answer,
        stopped_by="no_followup",
        rag_model=rag_model,
        followup_model=followup_model,
        started_at=started_at,
        finished_at=finished_at,
        latency_ms=max(0, round((perf_counter() - total_started) * 1000)),
        rag_calls=[call_record],
    )


async def run_adaptive_followup(
    case: PilotCase,
    *,
    rag_call: RagCallable = request_rag,
    policy: FollowUpPolicyLike | None = None,
    answer_provider: AnswerProvider | None = None,
    input_fn: InputCallable = input,
    output_fn: OutputCallable = print,
    experiment_id: str | None = None,
    rag_model: str = "existing-rag-service",
    followup_model: str = settings.chat_followup_policy_model,
    max_rounds: int = MAX_FOLLOWUP_ROUNDS,
) -> ExperimentResult:
    if not 1 <= max_rounds <= MAX_FOLLOWUP_ROUNDS:
        raise ValueError("max_rounds must be between 1 and 3")

    started_at = utc_now()
    total_started = perf_counter()
    initial_query = build_initial_query(case)
    current_query = initial_query
    latest_response, first_call = await _timed_rag_call(
        query=current_query,
        round_number=0,
        rag_call=rag_call,
    )
    rag_calls = [first_call]
    questions: list[QuestionRecord] = []
    exchanges: list[ClarificationExchange] = []
    stopped_by = "max_rounds"
    failure_reason: str | None = None
    active_policy = policy or AnthropicFollowUpPolicy()
    active_answer_provider = answer_provider
    if active_answer_provider is None:
        print_answer_sheet(case, output_fn)
        active_answer_provider = _interactive_answer_provider(
            input_fn=input_fn,
            output_fn=output_fn,
        )

    for round_number in range(1, max_rounds + 1):
        try:
            raw_decision = await active_policy.decide(
                original_user_content=initial_query,
                clarification_exchanges=tuple(exchanges),
                rag_answer=latest_response.answer,
            )
            decision = FollowUpDecision.model_validate(raw_decision)
        except Exception as exc:
            stopped_by = "policy_failure"
            failure_reason = type(exc).__name__
            break

        if decision.action == "answer":
            stopped_by = "policy_answer"
            break

        normalized = _normalize_question(decision.question)
        if any(_normalize_question(item.question) == normalized for item in questions):
            stopped_by = "policy_failure"
            failure_reason = "duplicate_question"
            break

        human_answer = active_answer_provider(case, round_number, decision.question)
        if not human_answer.answer.strip():
            raise ValueError("human answer must not be blank")
        question_record = QuestionRecord(
            round=round_number,
            question=decision.question,
            answer=human_answer.answer.strip(),
            is_compound=human_answer.is_compound,
            requested_fields=list(human_answer.requested_fields),
        )
        questions.append(question_record)
        exchanges.append(
            ClarificationExchange(
                question=question_record.question,
                answer=question_record.answer,
            )
        )
        current_query = build_clarified_query(
            original_user_content=initial_query,
            clarification_exchanges=tuple(exchanges),
        )
        latest_response, call_record = await _timed_rag_call(
            query=current_query,
            round_number=round_number,
            rag_call=rag_call,
        )
        rag_calls.append(call_record)
        if round_number == max_rounds:
            stopped_by = "max_rounds"

    finished_at = utc_now()
    return ExperimentResult(
        experiment_id=experiment_id or str(uuid4()),
        case_id=case.case_id,
        method="adaptive_followup",
        original_request=case.original_request,
        initial_context=case.initial_context,
        questions=questions,
        followup_rounds=len(questions),
        final_rag_query=current_query,
        final_analysis=latest_response.answer,
        stopped_by=stopped_by,
        failure_reason=failure_reason,
        rag_model=rag_model,
        followup_model=followup_model,
        started_at=started_at,
        finished_at=finished_at,
        latency_ms=max(0, round((perf_counter() - total_started) * 1000)),
        rag_calls=rag_calls,
    )


def save_result(
    result: ExperimentResult,
    results_dir: Path = DEFAULT_RESULTS_DIR,
) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = result.started_at.strftime("%Y%m%dT%H%M%SZ")
    path = results_dir / (
        f"{result.case_id}_{result.method}_{timestamp}_{result.experiment_id}.json"
    )
    path.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


async def run_method(
    case: PilotCase,
    method: Method,
    **kwargs: object,
) -> ExperimentResult:
    if method == "no_followup":
        allowed = {
            key: value
            for key, value in kwargs.items()
            if key in {"rag_call", "experiment_id", "rag_model", "followup_model"}
        }
        return await run_no_followup(case, **allowed)  # type: ignore[arg-type]
    return await run_adaptive_followup(case, **kwargs)  # type: ignore[arg-type]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, type=Path)
    parser.add_argument(
        "--method",
        required=True,
        choices=("no_followup", "adaptive_followup", "all"),
    )
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument(
        "--rag-model",
        default=os.getenv("RAG_MODEL_LABEL", "existing-rag-service"),
        help="Metadata label only; this does not alter RAG configuration.",
    )
    return parser


async def _run_cli(args: argparse.Namespace) -> list[Path]:
    case = load_case(args.case)
    experiment_id = str(uuid4())
    methods: tuple[Method, ...] = (
        ("no_followup", "adaptive_followup")
        if args.method == "all"
        else (args.method,)
    )
    saved: list[Path] = []
    for method in methods:
        result = await run_method(
            case,
            method,
            experiment_id=experiment_id,
            rag_model=args.rag_model,
        )
        path = save_result(result, args.results_dir)
        print(f"Saved {method}: {path}")
        saved.append(path)
    return saved


def main() -> None:
    args = build_argument_parser().parse_args()
    asyncio.run(_run_cli(args))


if __name__ == "__main__":
    main()


__all__ = [
    "HumanAnswer",
    "MAX_FOLLOWUP_ROUNDS",
    "OUTSIDE_ANSWER_SHEET",
    "build_initial_query",
    "load_case",
    "run_adaptive_followup",
    "run_method",
    "run_no_followup",
    "save_result",
]
