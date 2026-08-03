import app.models  # noqa: F401
from app.database import Base


def _constraint_names(table_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {constraint.name for constraint in table.constraints}


def test_only_chat_and_user_tables_are_registered_for_schema_creation() -> None:
    assert set(Base.metadata.tables) == {
        "chat_threads",
        "chat_messages",
        "chat_runs",
        "users",
    }


def test_chat_thread_constraints_are_registered() -> None:
    assert _constraint_names("chat_threads") == {
        "pk_chat_threads",
        "ck_chat_threads_status",
        "ck_chat_threads_next_message_ordinal_positive",
    }


def test_chat_message_foreign_keys_and_constraints_are_registered() -> None:
    table = Base.metadata.tables["chat_messages"]
    assert _constraint_names("chat_messages") == {
        "pk_chat_messages",
        "uq_chat_messages_thread_id_ordinal",
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
