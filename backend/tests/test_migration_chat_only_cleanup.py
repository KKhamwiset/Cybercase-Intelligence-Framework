import ast
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
import sqlalchemy as sa


BACKEND_ROOT = Path(__file__).parents[1]
MIGRATIONS = BACKEND_ROOT / "alembic" / "versions"
BASELINE_MIGRATIONS = BACKEND_ROOT / "alembic" / "baseline_versions"


def _load_migration(
    filename: str,
    directory: Path = MIGRATIONS,
) -> ModuleType:
    path = directory / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_graph_has_one_chat_only_head() -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option(
        "script_location",
        str(BACKEND_ROOT / "alembic"),
    )
    heads = ScriptDirectory.from_config(config).get_heads()

    assert heads == ["0005_rag_contexts"]


def test_answered_thread_status_migration_replaces_only_the_status_check(
    monkeypatch,
) -> None:
    migration = _load_migration(
        "0004_answered_thread_status.py",
        BASELINE_MIGRATIONS,
    )
    events: list[tuple[object, ...]] = []

    class _Operations:
        def drop_constraint(self, name: str, table_name: str, **kwargs: object) -> None:
            events.append(("drop_constraint", name, table_name, kwargs.get("type_")))

        def create_check_constraint(
            self,
            name: str,
            table_name: str,
            condition: str,
        ) -> None:
            events.append(("create_check_constraint", name, table_name, condition))

    monkeypatch.setattr(migration, "op", _Operations())

    assert migration.revision == "0004_answered_thread_status"
    assert migration.down_revision == "0003_case_state_versions"

    migration.upgrade()
    assert events == [
        (
            "drop_constraint",
            "ck_chat_threads_status",
            "chat_threads",
            "check",
        ),
        (
            "create_check_constraint",
            "ck_chat_threads_status",
            "chat_threads",
            "status IN ('idle', 'processing', 'awaiting_followup', 'answered', 'failed')",
        ),
    ]

    events.clear()
    migration.downgrade()
    assert events == [
        (
            "drop_constraint",
            "ck_chat_threads_status",
            "chat_threads",
            "check",
        ),
        (
            "create_check_constraint",
            "ck_chat_threads_status",
            "chat_threads",
            "status IN ('idle', 'processing', 'awaiting_followup', 'failed')",
        ),
    ]


def test_case_state_version_migration_upgrade_and_downgrade_are_ordered(
    monkeypatch,
) -> None:
    migration = _load_migration(
        "0003_case_state_versions.py",
        BASELINE_MIGRATIONS,
    )
    source = (
        BASELINE_MIGRATIONS / "0003_case_state_versions.py"
    ).read_text(encoding="utf-8")
    events: list[tuple[object, ...]] = []
    created_elements: tuple[object, ...] = ()

    class _Operations:
        def create_unique_constraint(
            self,
            name: str,
            table_name: str,
            columns: list[str],
        ) -> None:
            events.append(
                ("create_unique_constraint", name, table_name, tuple(columns))
            )

        def create_table(self, name: str, *elements: object) -> None:
            nonlocal created_elements
            created_elements = elements
            events.append(("create_table", name))

        def create_index(
            self,
            name: str,
            table_name: str,
            columns: list[str],
            **kwargs: object,
        ) -> None:
            events.append(
                (
                    "create_index",
                    name,
                    table_name,
                    tuple(columns),
                    bool(kwargs.get("unique")),
                )
            )

        def add_column(self, table_name: str, column: sa.Column) -> None:
            events.append(("add_column", table_name, column.name))

        def create_foreign_key(
            self,
            name: str,
            source_table: str,
            referent_table: str,
            local_columns: list[str],
            remote_columns: list[str],
            **kwargs: object,
        ) -> None:
            events.append(
                (
                    "create_foreign_key",
                    name,
                    source_table,
                    referent_table,
                    tuple(local_columns),
                    tuple(remote_columns),
                    kwargs.get("ondelete"),
                )
            )

        def drop_constraint(
            self,
            name: str,
            table_name: str,
            **kwargs: object,
        ) -> None:
            events.append(
                ("drop_constraint", name, table_name, kwargs.get("type_"))
            )

        def drop_column(self, table_name: str, column_name: str) -> None:
            events.append(("drop_column", table_name, column_name))

        def drop_index(
            self,
            name: str,
            **kwargs: object,
        ) -> None:
            events.append(("drop_index", name, kwargs.get("table_name")))

        def drop_table(self, name: str) -> None:
            events.append(("drop_table", name))

    monkeypatch.setattr(migration, "op", _Operations())

    assert migration.revision == "0003_case_state_versions"
    assert migration.down_revision == "0002_chat_reports"
    assert "op.execute" not in source
    assert "op.bulk_insert" not in source

    migration.upgrade()

    assert events == [
        (
            "create_unique_constraint",
            "uq_chat_messages_thread_id_id",
            "chat_messages",
            ("thread_id", "id"),
        ),
        ("create_table", "case_state_versions"),
        (
            "create_index",
            "ix_case_state_versions_thread_id_created_at",
            "case_state_versions",
            ("thread_id", "created_at"),
            False,
        ),
        (
            "add_column",
            "chat_threads",
            "current_case_state_version_id",
        ),
        (
            "create_foreign_key",
            "fk_chat_threads_current_case_state_version",
            "chat_threads",
            "case_state_versions",
            ("id", "current_case_state_version_id"),
            ("thread_id", "id"),
            None,
        ),
    ]
    assert {
        element.name
        for element in created_elements
        if isinstance(element, sa.Column)
    } == {
        "id",
        "thread_id",
        "version",
        "parent_version_id",
        "trigger_message_id",
        "delta_json",
        "state_json",
        "created_at",
    }
    assert {
        element.name
        for element in created_elements
        if isinstance(element, sa.Constraint)
    } == {
        "pk_case_state_versions",
        "uq_case_state_versions_thread_id_version",
        "uq_case_state_versions_thread_id_id",
        "ck_case_state_versions_version_positive",
        "fk_case_state_versions_thread_id_chat_threads",
        "fk_case_state_versions_thread_parent",
        "fk_case_state_versions_thread_trigger_message",
    }

    events.clear()
    migration.downgrade()

    assert events == [
        (
            "drop_constraint",
            "fk_chat_threads_current_case_state_version",
            "chat_threads",
            "foreignkey",
        ),
        (
            "drop_column",
            "chat_threads",
            "current_case_state_version_id",
        ),
        (
            "drop_index",
            "ix_case_state_versions_thread_id_created_at",
            "case_state_versions",
        ),
        ("drop_table", "case_state_versions"),
        (
            "drop_constraint",
            "uq_chat_messages_thread_id_id",
            "chat_messages",
            "unique",
        ),
    ]


def test_rag_context_migration_upgrade_and_downgrade_are_ordered(
    monkeypatch,
) -> None:
    migration = _load_migration(
        "0005_rag_contexts.py",
        BASELINE_MIGRATIONS,
    )
    events: list[tuple[object, ...]] = []
    created_elements: tuple[object, ...] = ()

    class _Operations:
        def create_table(self, name: str, *elements: object) -> None:
            nonlocal created_elements
            created_elements = elements
            events.append(("create_table", name))

        def drop_table(self, name: str) -> None:
            events.append(("drop_table", name))

    monkeypatch.setattr(migration, "op", _Operations())

    assert migration.revision == "0005_rag_contexts"
    assert migration.down_revision == "0004_answered_thread_status"

    migration.upgrade()

    assert events == [("create_table", "rag_contexts")]
    columns = {
        element.name: element
        for element in created_elements
        if isinstance(element, sa.Column)
    }
    assert set(columns) == {
        "retrieval_context_id",
        "thread_id",
        "case_state_version_id",
        "context",
        "mitre_table",
        "created_at",
    }
    assert columns["retrieval_context_id"].type.length == 160
    assert str(columns["mitre_table"].server_default.arg) == "'[]'::jsonb"
    assert {
        element.name
        for element in created_elements
        if isinstance(element, sa.Constraint)
    } == {
        "pk_rag_contexts",
        "uq_rag_contexts_case_state_version_id",
        "fk_rag_contexts_thread_case_state_version",
    }

    events.clear()
    migration.downgrade()

    assert events == [("drop_table", "rag_contexts")]


def test_chat_user_baseline_declares_the_retained_schema_explicitly(
    monkeypatch,
) -> None:
    migration = _load_migration(
        "0001_chat_user_baseline.py",
        BASELINE_MIGRATIONS,
    )
    source = (BASELINE_MIGRATIONS / "0001_chat_user_baseline.py").read_text(
        encoding="utf-8"
    )
    assert migration.revision == "0001_chat_user_baseline"
    assert migration.down_revision is None
    assert "create_all" not in source
    assert "Base.metadata" not in source

    created_tables: dict[str, tuple[object, ...]] = {}
    created_indexes: list[tuple[str, str, tuple[str, ...], bool]] = []

    class _Operations:
        def create_table(self, name: str, *elements: object) -> None:
            created_tables[name] = elements

        def create_index(
            self,
            name: str,
            table_name: str,
            columns: list[str],
            **kwargs: object,
        ) -> None:
            created_indexes.append(
                (name, table_name, tuple(columns), bool(kwargs.get("unique")))
            )

    monkeypatch.setattr(migration, "op", _Operations())
    migration.upgrade()

    assert list(created_tables) == [
        "users",
        "chat_threads",
        "chat_messages",
        "chat_runs",
    ]
    assert {
        column.name
        for column in created_tables["users"]
        if isinstance(column, sa.Column)
    } == {"id", "email", "display_name", "created_at", "updated_at"}
    assert {
        column.name
        for column in created_tables["chat_threads"]
        if isinstance(column, sa.Column)
    } == {
        "id",
        "title",
        "status",
        "active_rag_session_id",
        "next_message_ordinal",
        "created_at",
        "updated_at",
    }
    assert {
        column.name
        for column in created_tables["chat_messages"]
        if isinstance(column, sa.Column)
    } == {
        "id",
        "thread_id",
        "ordinal",
        "role",
        "content",
        "retrieval_context_id",
        "metadata_json",
        "created_at",
    }
    assert {
        column.name
        for column in created_tables["chat_runs"]
        if isinstance(column, sa.Column)
    } == {
        "id",
        "thread_id",
        "request_message_id",
        "operation",
        "status",
        "input_rag_session_id",
        "idempotency_key",
        "request_fingerprint",
        "request_payload",
        "attempt_count",
        "lease_owner",
        "lease_expires_at",
        "error_code",
        "error_message",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    }
    assert created_indexes == [
        ("ix_users_email", "users", ("email",), True),
        ("ix_chat_threads_updated_at", "chat_threads", ("updated_at",), False),
        (
            "ix_chat_runs_status_lease_expires_at",
            "chat_runs",
            ("status", "lease_expires_at"),
            False,
        ),
        (
            "ix_chat_runs_thread_id_created_at",
            "chat_runs",
            ("thread_id", "created_at"),
            False,
        ),
        ("ux_chat_runs_one_active_per_thread", "chat_runs", ("thread_id",), True),
    ]


def test_chat_user_baseline_downgrade_is_explicitly_irreversible() -> None:
    migration = _load_migration(
        "0001_chat_user_baseline.py",
        BASELINE_MIGRATIONS,
    )

    with pytest.raises(RuntimeError, match="verified backup"):
        migration.downgrade()


def test_case_chat_migration_is_self_contained_and_hashes_canonically() -> None:
    path = MIGRATIONS / "0003_case_chat_state.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not any(
        module == "app" or module.startswith("app.")
        for module in imported_modules
    )

    migration = _load_migration("0003_case_chat_state.py")
    payload = migration._build_payload_from_values(
        title="  Incident  ",
        status="open",
        severity="high",
        data={
            "affected_assets": ["z-host", "a-host"],
            "timeline_events": [
                {"event_id": "2", "title": "Second"},
                {"event_id": "1", "title": "First"},
            ],
            "analyst_notes": "line one  \r\nline two  ",
            "transient": "excluded",
        },
    )

    assert payload["title"] == "Incident"
    assert payload["affected_assets"] == ["a-host", "z-host"]
    assert [item["event_id"] for item in payload["timeline_events"]] == ["1", "2"]
    assert payload["analyst_notes"] == "line one\nline two"
    assert "transient" not in payload
    assert migration._snapshot_hash(payload) == (
        "be2cf1e6df5e0b9735e0a670bac8ffdec8be06a903709c2c8c7d7a611004ce22"
    )


def test_cleanup_preflights_and_explicitly_drops_in_dependency_order() -> None:
    path = MIGRATIONS / "0008_chat_user_only_cleanup.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    upgrade = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "upgrade"
    )
    calls = [
        node.value
        for node in upgrade.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    ]

    assert isinstance(calls[0].func, ast.Name)
    assert calls[0].func.id == "_preflight_inbound_foreign_keys"
    assert [
        call.args[0].value
        for call in calls[1:]
        if isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "op"
        and call.func.attr == "drop_table"
        and isinstance(call.args[0], ast.Constant)
    ] == [
        "retrieval_snapshots",
        "report_sessions",
        "reports",
        "case_chat_turns",
        "case_chat_states",
        "cases",
    ]
    migration = _load_migration("0008_chat_user_only_cleanup.py")
    assert migration.RETAINED_TABLES == (
        "users",
        "chat_threads",
        "chat_messages",
        "chat_runs",
    )
    assert "users" not in migration.DROP_TABLES
    assert "retrieval_snapshots" in migration.DROP_TABLES
    assert "pg_constraint" in source
    assert "unexpected inbound foreign" in source
    assert "cascade" not in source.casefold()


def test_cleanup_downgrade_is_explicitly_irreversible() -> None:
    migration = _load_migration("0008_chat_user_only_cleanup.py")

    with pytest.raises(RuntimeError, match="verified backup"):
        migration.downgrade()


def test_cleanup_preflight_aborts_on_unexpected_inbound_foreign_key(
    monkeypatch,
) -> None:
    migration = _load_migration("0008_chat_user_only_cleanup.py")

    class _Result:
        def mappings(self):
            return self

        def all(self):
            return [
                {
                    "source_schema": "public",
                    "source_table": "chat_threads",
                    "constraint_name": "fk_chat_threads_case_id",
                    "target_table": "cases",
                }
            ]

    class _Bind:
        def execute(self, statement):
            return _Result()

    monkeypatch.setattr(migration.op, "get_bind", lambda: _Bind())

    with pytest.raises(
        RuntimeError,
        match=(
            "public.chat_threads.fk_chat_threads_case_id -> cases"
        ),
    ):
        migration._preflight_inbound_foreign_keys()
