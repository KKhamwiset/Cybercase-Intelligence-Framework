import app.models  # noqa: F401
from sqlalchemy import inspect
from sqlalchemy.orm import configure_mappers

from app.database import Base
from app.models.chat import ChatThread


def _constraint_names(table_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {constraint.name for constraint in table.constraints}


def test_retained_tables_are_registered_for_schema_creation() -> None:
    assert set(Base.metadata.tables) == {
        "case_state_versions",
        "chat_threads",
        "chat_messages",
        "chat_runs",
        "chat_reports",
        "rag_contexts",
        "users",
    }


def test_chat_thread_constraints_are_registered() -> None:
    assert _constraint_names("chat_threads") == {
        "pk_chat_threads",
        "ck_chat_threads_status",
        "ck_chat_threads_next_message_ordinal_positive",
        "fk_chat_threads_current_case_state_version",
    }

    table = Base.metadata.tables["chat_threads"]
    status_constraint = next(
        constraint
        for constraint in table.constraints
        if constraint.name == "ck_chat_threads_status"
    )
    assert "answered" in str(status_constraint.sqltext)
    assert {
        (foreign_key.parent.name, foreign_key.target_fullname, foreign_key.ondelete)
        for foreign_key in table.foreign_keys
    } == {
        (
            "id",
            "case_state_versions.thread_id",
            None,
        ),
        (
            "current_case_state_version_id",
            "case_state_versions.id",
            None,
        )
    }


def test_chat_message_foreign_keys_and_constraints_are_registered() -> None:
    table = Base.metadata.tables["chat_messages"]
    assert _constraint_names("chat_messages") == {
        "pk_chat_messages",
        "uq_chat_messages_thread_id_ordinal",
        "uq_chat_messages_thread_id_id",
        "ck_chat_messages_ordinal_positive",
        "ck_chat_messages_role",
        "fk_chat_messages_thread_id_chat_threads",
    }
    assert {
        (foreign_key.parent.name, foreign_key.target_fullname, foreign_key.ondelete)
        for foreign_key in table.foreign_keys
    } == {("thread_id", "chat_threads.id", "CASCADE")}


def test_chat_run_foreign_keys_and_constraints_are_registered() -> None:
    table = Base.metadata.tables["chat_runs"]
    assert _constraint_names("chat_runs") == {
        "pk_chat_runs",
        "uq_chat_runs_thread_id_idempotency_key",
        "ck_chat_runs_operation",
        "ck_chat_runs_status",
        "ck_chat_runs_input_rag_session_id",
        "ck_chat_runs_attempt_count_nonnegative",
        "fk_chat_runs_request_message_id_chat_messages",
        "fk_chat_runs_thread_id_chat_threads",
    }
    assert {
        (foreign_key.parent.name, foreign_key.target_fullname, foreign_key.ondelete)
        for foreign_key in table.foreign_keys
    } == {
        ("request_message_id", "chat_messages.id", "CASCADE"),
        ("thread_id", "chat_threads.id", "CASCADE"),
    }


def test_chat_report_foreign_keys_and_constraints_are_registered() -> None:
    table = Base.metadata.tables["chat_reports"]
    assert _constraint_names("chat_reports") == {
        "pk_chat_reports",
        "uq_chat_reports_thread_id_version_number",
        "uq_chat_reports_thread_id_idempotency_key",
        "ck_chat_reports_version_number_positive",
        "ck_chat_reports_status",
        "ck_chat_reports_validation_status",
        "fk_chat_reports_extraction_message_id_chat_messages",
        "fk_chat_reports_thread_id_chat_threads",
    }
    assert {
        (foreign_key.parent.name, foreign_key.target_fullname, foreign_key.ondelete)
        for foreign_key in table.foreign_keys
    } == {
        ("extraction_message_id", "chat_messages.id", "CASCADE"),
        ("thread_id", "chat_threads.id", "CASCADE"),
    }


def test_case_state_version_foreign_keys_and_constraints_are_registered() -> None:
    table = Base.metadata.tables["case_state_versions"]
    assert _constraint_names("case_state_versions") == {
        "pk_case_state_versions",
        "uq_case_state_versions_thread_id_version",
        "uq_case_state_versions_thread_id_id",
        "ck_case_state_versions_version_positive",
        "fk_case_state_versions_thread_id_chat_threads",
        "fk_case_state_versions_thread_parent",
        "fk_case_state_versions_thread_trigger_message",
    }
    assert {
        (foreign_key.parent.name, foreign_key.target_fullname, foreign_key.ondelete)
        for foreign_key in table.foreign_keys
    } == {
        ("thread_id", "chat_threads.id", "CASCADE"),
        ("thread_id", "case_state_versions.thread_id", None),
        ("parent_version_id", "case_state_versions.id", None),
        ("thread_id", "chat_messages.thread_id", None),
        ("trigger_message_id", "chat_messages.id", None),
    }
    assert set(table.indexes).pop().name == (
        "ix_case_state_versions_thread_id_created_at"
    )


def test_case_state_relationships_configure_without_ambiguous_foreign_keys() -> None:
    configure_mappers()
    relationships = inspect(ChatThread).relationships

    assert {column.name for column in relationships.case_state_versions.local_columns} == {
        "id"
    }
    assert {
        column.name for column in relationships.current_case_state_version.local_columns
    } == {"current_case_state_version_id"}


def test_rag_context_constraints_bind_one_context_to_the_same_thread_version() -> None:
    table = Base.metadata.tables["rag_contexts"]
    assert _constraint_names("rag_contexts") == {
        "pk_rag_contexts",
        "uq_rag_contexts_case_state_version_id",
        "fk_rag_contexts_thread_case_state_version",
    }
    assert {
        (foreign_key.parent.name, foreign_key.target_fullname, foreign_key.ondelete)
        for foreign_key in table.foreign_keys
    } == {
        ("thread_id", "case_state_versions.thread_id", "CASCADE"),
        ("case_state_version_id", "case_state_versions.id", "CASCADE"),
    }
    assert table.c.retrieval_context_id.type.length == 160
    unique_constraint = next(
        constraint
        for constraint in table.constraints
        if constraint.name == "uq_rag_contexts_case_state_version_id"
    )
    assert [column.name for column in unique_constraint.columns] == [
        "case_state_version_id"
    ]
    assert table.c.context.nullable is False
    assert table.c.mitre_table.nullable is False
    assert str(table.c.mitre_table.server_default.arg) == "'[]'::jsonb"
