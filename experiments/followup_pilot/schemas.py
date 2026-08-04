"""Strict, serializable contracts for the follow-up pilot."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Method = Literal["no_followup", "adaptive_followup"]
StoppedBy = Literal[
    "policy_answer",
    "max_rounds",
    "no_followup",
    "policy_failure",
]
FieldRating = Literal[
    "correct_supported",
    "missing",
    "incorrect",
    "unsupported",
]
HiddenField = Literal["affected_account", "initial_access"]

REQUIRED_REFERENCE_FIELDS = (
    "incident_type",
    "affected_account",
    "initial_access",
    "phishing_time",
    "unauthorized_login_time",
    "source_ip",
    "attacker_action",
    "impact",
    "response_actions",
    "data_exfiltration",
)
RECOVERABLE_HIDDEN_FIELDS = ("affected_account", "initial_access")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PilotCase(StrictModel):
    case_id: str
    language: str
    original_request: str
    initial_context: str
    hidden_answers: dict[str, str]
    unknown_information: dict[str, str]
    reference_fields: dict[str, str]

    @model_validator(mode="after")
    def validate_case_contract(self) -> "PilotCase":
        if set(self.hidden_answers) != set(RECOVERABLE_HIDDEN_FIELDS):
            raise ValueError(
                "hidden_answers must contain exactly affected_account and initial_access"
            )
        if tuple(self.reference_fields) != REQUIRED_REFERENCE_FIELDS:
            raise ValueError("reference_fields must use the fixed pilot checklist order")
        if set(self.unknown_information) != {"data_exfiltration"}:
            raise ValueError("only data_exfiltration may be marked unknown")
        return self


class QuestionRecord(StrictModel):
    round: int = Field(ge=1, le=3)
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    is_compound: bool
    requested_fields: list[HiddenField] = Field(default_factory=list)

    @model_validator(mode="after")
    def requested_fields_are_unique(self) -> "QuestionRecord":
        if len(self.requested_fields) != len(set(self.requested_fields)):
            raise ValueError("requested_fields must not contain duplicates")
        return self


class RagCallRecord(StrictModel):
    round: int = Field(ge=0, le=3)
    query: str = Field(min_length=1)
    retrieval_context_id: str | None = None
    latency_ms: int = Field(ge=0)


class ExperimentResult(StrictModel):
    experiment_id: str
    case_id: str
    method: Method
    original_request: str
    initial_context: str
    questions: list[QuestionRecord]
    followup_rounds: int = Field(ge=0, le=3)
    final_rag_query: str
    final_analysis: str
    stopped_by: StoppedBy
    failure_reason: str | None = None
    rag_model: str
    followup_model: str
    started_at: datetime
    finished_at: datetime
    latency_ms: int = Field(ge=0)
    rag_calls: list[RagCallRecord]


class SystemMetrics(StrictModel):
    analysis_completeness: float = Field(ge=0.0, le=1.0)
    hidden_field_recovery: float = Field(ge=0.0, le=1.0)
    final_hidden_field_utilization: float = Field(ge=0.0, le=1.0)
    questions_asked: int = Field(ge=0)
    exact_duplicate_question_count: int = Field(ge=0)
    compound_question_count: int = Field(ge=0)
    unsupported_field_count: int = Field(ge=0)


class SystemEvaluation(StrictModel):
    experiment_id: str
    field_scores: dict[str, FieldRating]
    metrics: SystemMetrics


class EvaluationResult(StrictModel):
    evaluation_id: str
    case_id: str
    systems: dict[str, SystemEvaluation]
    mapping: dict[str, Method]
    started_at: datetime
    finished_at: datetime


__all__ = [
    "EvaluationResult",
    "ExperimentResult",
    "FieldRating",
    "HiddenField",
    "Method",
    "PilotCase",
    "QuestionRecord",
    "RagCallRecord",
    "RECOVERABLE_HIDDEN_FIELDS",
    "REQUIRED_REFERENCE_FIELDS",
    "SystemEvaluation",
    "SystemMetrics",
]
