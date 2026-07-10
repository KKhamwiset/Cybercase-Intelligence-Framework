from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_migration() -> ModuleType:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0005_single_report_per_case.py"
    )
    spec = importlib.util.spec_from_file_location(
        "migration_0005_single_report_per_case",
        migration_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_deduplicates_newest_report_before_adding_unique_constraint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration()
    actions: list[tuple[object, ...]] = []

    monkeypatch.setattr(
        migration.op,
        "execute",
        lambda statement: actions.append(("execute", str(statement))),
    )
    monkeypatch.setattr(
        migration.op,
        "drop_index",
        lambda name, **kwargs: actions.append(("drop_index", name, kwargs)),
    )
    monkeypatch.setattr(
        migration.op,
        "create_unique_constraint",
        lambda name, table, columns: actions.append(
            ("create_unique_constraint", name, table, columns)
        ),
    )

    migration.upgrade()

    normalized_sql = " ".join(str(actions[0][1]).split())
    assert "ROW_NUMBER() OVER" in normalized_sql
    assert "PARTITION BY case_id" in normalized_sql
    assert (
        "ORDER BY created_at DESC, updated_at DESC, report_id DESC"
        in normalized_sql
    )
    assert "report_rank > 1" in normalized_sql
    assert actions[1:] == [
        ("drop_index", "ix_reports_case_id", {"table_name": "reports"}),
        (
            "create_unique_constraint",
            "uq_reports_case_id",
            "reports",
            ["case_id"],
        ),
    ]


def test_downgrade_restores_nonunique_case_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration()
    actions: list[tuple[object, ...]] = []

    monkeypatch.setattr(
        migration.op,
        "drop_constraint",
        lambda name, table, **kwargs: actions.append(
            ("drop_constraint", name, table, kwargs)
        ),
    )
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda name, table, columns, **kwargs: actions.append(
            ("create_index", name, table, columns, kwargs)
        ),
    )

    migration.downgrade()

    assert actions == [
        (
            "drop_constraint",
            "uq_reports_case_id",
            "reports",
            {"type_": "unique"},
        ),
        (
            "create_index",
            "ix_reports_case_id",
            "reports",
            ["case_id"],
            {"unique": False},
        ),
    ]
