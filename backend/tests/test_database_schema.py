from app.database import Base
from app.models.case import CaseRecord


def test_cases_table_is_registered_for_schema_creation() -> None:
    assert CaseRecord.__tablename__ in Base.metadata.tables
    table = Base.metadata.tables[CaseRecord.__tablename__]

    assert {"case_id", "title", "status", "severity", "data"}.issubset(table.columns.keys())
