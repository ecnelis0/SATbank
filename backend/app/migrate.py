"""Bringing the database up to date, safely.

Replaces `create_all`, which could only ever create missing tables - it would not
add a column to a table that already existed, so six schema changes were applied by
hand and the seventh would have failed at run time with `no such column`.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from .config import get_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = Path.home() / "Documents" / "sat_bank-backups"
KEEP_BACKUPS = 20


def _config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    return config


def sqlite_path(url: str) -> Path | None:
    """The file behind a SQLite URL, or None for anything else."""
    if not url.startswith("sqlite"):
        return None
    _, _, tail = url.partition("///")
    if not tail:
        return None
    path = Path(tail)
    return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


def back_up(url: str) -> Path | None:
    """Copy the database aside before touching its schema.

    A migration is the one routine operation that can destroy a bank, so it is the
    one place worth spending a copy. Postgres is left to its own backups.
    """
    path = sqlite_path(url)
    if path is None or not path.exists():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    destination = BACKUP_DIR / f"{path.stem}-{stamp}.db"
    shutil.copy2(path, destination)

    # Keep the recent ones; an unbounded backup directory is its own problem.
    existing = sorted(BACKUP_DIR.glob(f"{path.stem}-*.db"))
    for stale in existing[:-KEEP_BACKUPS]:
        stale.unlink(missing_ok=True)

    return destination


def pending() -> bool:
    """Is the database behind the migrations on disk?"""
    url = get_settings().database_url
    sync_url = url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg")
    script = ScriptDirectory.from_config(_config())
    head = script.get_current_head()

    engine = create_engine(sync_url)
    try:
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()
    return current != head


def upgrade() -> Path | None:
    """Migrate to head, backing up first if there is anything to do."""
    url = get_settings().database_url
    backup = back_up(url) if pending() else None
    command.upgrade(_config(), "head")
    return backup
