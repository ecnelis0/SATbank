"""one rung at a time: 24h / 1w / 1mo / 3mo, a miss repeats the rung

Revision ID: 7c2e9a1d4b60
Revises: 1af4ac33593e
Create Date: 2026-10-17 15:30:00

Data only - the table is unchanged. The old ladder armed all five rungs (1h,
24h, 72h, 1w, 1mo) at logging and restarted all of them on a miss. The new one
keeps a single open rung per question. For every question this keeps the open
rung the student had reached, moved onto the new ladder with its due date
unchanged, and retires the rest as `superseded` - never deleted, so the history
of what was answered stays intact.

    1h, 24h  -> 24h      72h, 1w -> 1w      1mo -> 1mo

A question that had already passed its 1-month review gets the new 3-month one.
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.models

revision: str = "7c2e9a1d4b60"
down_revision: Union[str, Sequence[str], None] = "1af4ac33593e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_TO_NEW = {"1h": "24h", "24h": "24h", "72h": "1w", "1w": "1w", "1mo": "1mo"}
NEW_STEP = {"24h": 0, "1w": 1, "1mo": 2, "3mo": 3}

events = sa.table(
    "review_events",
    sa.column("id", sa.String),
    sa.column("mistake_id", sa.String),
    sa.column("cycle", sa.Integer),
    sa.column("step_index", sa.Integer),
    sa.column("interval_label", sa.String),
    sa.column("due_at", app.models.UtcDateTime()),
    sa.column("completed_at", app.models.UtcDateTime()),
    sa.column("outcome", sa.String),
)


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)
    rows = bind.execute(sa.select(events)).mappings().all()

    by_mistake: dict[str, list] = defaultdict(list)
    for row in rows:
        by_mistake[row["mistake_id"]].append(row)

    for mistake_id, rungs in by_mistake.items():
        open_rungs = sorted(
            (r for r in rungs if r["completed_at"] is None), key=lambda r: r["due_at"]
        )

        if open_rungs:
            target = OLD_TO_NEW.get(open_rungs[0]["interval_label"])
            if target is None:
                continue
            keep = next(
                (r for r in open_rungs if r["interval_label"] == target), open_rungs[0]
            )
            bind.execute(
                events.update()
                .where(events.c.id == keep["id"])
                .values(interval_label=target, step_index=NEW_STEP[target], cycle=0)
            )
            retire = [r["id"] for r in open_rungs if r["id"] != keep["id"]]
            if retire:
                bind.execute(
                    events.update()
                    .where(events.c.id.in_(retire))
                    .values(completed_at=now, outcome="superseded")
                )
            continue

        answered = sorted(
            (r for r in rungs if r["outcome"] in ("correct", "wrong", "skipped")),
            key=lambda r: r["completed_at"],
        )
        if answered and answered[-1]["interval_label"] == "1mo" and answered[-1]["outcome"] == "correct":
            bind.execute(
                events.insert().values(
                    id=uuid.uuid4().hex,
                    mistake_id=mistake_id,
                    cycle=0,
                    step_index=NEW_STEP["3mo"],
                    interval_label="3mo",
                    due_at=answered[-1]["completed_at"] + timedelta(days=90),
                    completed_at=None,
                    outcome=None,
                )
            )


def downgrade() -> None:
    # Not reversible: the retired rungs are marked superseded, and which of them
    # were open before cannot be told apart from ones superseded by a real miss.
    # The pre-migration backup in ~/Documents/sat_bank-backups is the way back.
    pass
