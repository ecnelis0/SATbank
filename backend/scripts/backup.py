"""Copy the bank aside, now.

Migrations back up automatically; this is for the other times - before an
experiment, or on a schedule. Run it with `uv run python scripts/backup.py`.
"""

from __future__ import annotations

import sys

from app.config import get_settings
from app.migrate import BACKUP_DIR, back_up, sqlite_path


def main() -> int:
    url = get_settings().database_url
    path = sqlite_path(url)

    if path is None:
        print(f"{url.split('://')[0]} is not a file database - use its own backup tool.")
        return 1
    if not path.exists():
        print(f"No database at {path} yet; nothing to copy.")
        return 1

    destination = back_up(url)
    kept = sorted(BACKUP_DIR.glob(f"{path.stem}-*.db"))
    size = destination.stat().st_size // 1024 if destination else 0
    print(f"Backed up {path.name} ({size}KB) to {destination}")
    print(f"{len(kept)} backup(s) kept in {BACKUP_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
