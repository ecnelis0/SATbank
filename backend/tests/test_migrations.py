"""Migrations. The point of these is that the seventh schema change is not by hand.

Six were, because `create_all` silently declines to alter a table that already
exists: the app kept starting cleanly and then failing on the first query with
`no such column`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.script import ScriptDirectory

from app import config
from app.migrate import _config, back_up, pending, sqlite_path, upgrade
from app.models import Base


@pytest.fixture
def blank(tmp_path, monkeypatch):
    """A database file that does not exist yet."""
    path = tmp_path / "fresh.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{path}")
    config.get_settings.cache_clear()
    yield path
    config.get_settings.cache_clear()


def tables(path: Path) -> set[str]:
    db = sqlite3.connect(path)
    try:
        return {r[0] for r in db.execute("select name from sqlite_master where type='table'")} - {
            "alembic_version"
        }
    finally:
        db.close()


def columns(path: Path, table: str) -> set[str]:
    db = sqlite3.connect(path)
    try:
        return {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
    finally:
        db.close()


def test_there_is_exactly_one_head(blank):
    """Two heads means someone branched the history and migrations will not apply."""
    script = ScriptDirectory.from_config(_config())

    assert len(script.get_heads()) == 1


def test_migrating_a_blank_database_builds_the_whole_schema(blank):
    upgrade()

    assert tables(blank) == set(Base.metadata.tables)


def test_every_column_matches_the_models(blank):
    """The check `create_all` could not do: columns, not just tables."""
    upgrade()

    for table in sorted(Base.metadata.tables):
        expected = {column.name for column in Base.metadata.tables[table].columns}
        assert columns(blank, table) == expected, table


def test_migrating_twice_is_a_no_op(blank):
    upgrade()
    before = tables(blank)

    upgrade()

    assert tables(blank) == before


def test_pending_is_true_before_and_false_after(blank):
    assert pending() is True

    upgrade()

    assert pending() is False


def test_the_schema_has_no_undeclared_drift(blank):
    """Autogenerate against a migrated database should find nothing to do.

    If this fails, someone changed a model without writing a migration - which is
    the exact failure the whole of this file exists to prevent.
    """
    from alembic.autogenerate import compare_metadata
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    upgrade()

    engine = create_engine(f"sqlite:///{blank}")
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    # Foreign keys and indexes reflect differently on SQLite; real drift is a
    # missing or extra table or column.
    real = [
        entry
        for entry in diff
        if isinstance(entry, tuple)
        and entry[0] in {"add_table", "remove_table", "add_column", "remove_column"}
    ]
    assert real == [], real


def test_a_migration_backs_the_database_up_first(blank):
    """A migration is the one routine operation that can destroy a bank."""
    upgrade()  # creates the file
    assert blank.exists()

    # back_up takes the database URL, not a bare path.
    backup = back_up(f"sqlite+aiosqlite:///{blank}")

    assert backup is not None and backup.exists()
    assert backup.stat().st_size == blank.stat().st_size
    backup.unlink()


def test_nothing_is_backed_up_when_there_is_nothing_to_migrate(blank):
    upgrade()
    first = upgrade()

    # Already at head, so no copy was taken.
    assert first is None


def test_a_postgres_url_is_left_to_its_own_backups(blank):
    assert sqlite_path("postgresql+asyncpg://user:pw@host/db") is None
    assert back_up("postgresql+asyncpg://user:pw@host/db") is None


def test_a_relative_sqlite_path_resolves_next_to_the_backend(blank):
    resolved = sqlite_path("sqlite+aiosqlite:///./sat_bank.db")

    assert resolved is not None and resolved.is_absolute()
    assert resolved.parent.name == "backend"


def test_the_migration_can_be_rolled_back(blank):
    upgrade()
    assert tables(blank)

    command.downgrade(_config(), "base")

    assert tables(blank) == set()
