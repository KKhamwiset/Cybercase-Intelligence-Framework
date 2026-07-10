from app.database import Base
from app.models.case import CaseRecord
from app.models.case_chat import CaseChatTurn
from app.models.case_chat import CaseChatState
from app.models.report import ReportRecord, ReportSessionRecord


def test_cases_table_is_registered_for_schema_creation() -> None:
    assert CaseRecord.__tablename__ in Base.metadata.tables
    table = Base.metadata.tables[CaseRecord.__tablename__]

    assert {"case_id", "title", "status", "severity", "data"}.issubset(table.columns.keys())


def test_case_chat_turns_register_structured_analysis_outputs() -> None:
    table = Base.metadata.tables[CaseChatTurn.__tablename__]
    assert "analysis_outputs_json" in table.columns
    assert table.columns["analysis_outputs_json"].nullable is False


def test_case_dependents_use_database_cascade_deletes() -> None:
    for model in (CaseChatState, CaseChatTurn, ReportRecord, ReportSessionRecord):
        table = Base.metadata.tables[model.__tablename__]
        case_fk = next(iter(table.columns["case_id"].foreign_keys))
        assert case_fk.ondelete == "CASCADE"


def test_reports_enforce_one_case_owned_record() -> None:
    table = Base.metadata.tables[ReportRecord.__tablename__]

    unique_case_constraints = {
        constraint.name
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
        and {column.name for column in constraint.columns} == {"case_id"}
    }

    assert unique_case_constraints == {"uq_reports_case_id"}
    assert CaseRecord.report.property.uselist is False
    assert "ix_reports_case_id" not in {index.name for index in table.indexes}
