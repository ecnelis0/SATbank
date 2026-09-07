"""The review ladder.

Every mistake is re-surfaced on the same fixed schedule, measured from the moment
it was logged: 1 hour, 24 hours, 72 hours, 1 week, 1 month. The intervals are
absolute and identical for every card - this is deliberately not SM-2/Anki, where
an ease factor stretches the gaps per card.

Missing a review restarts the ladder from the current time, so a card you are still
getting wrong keeps coming back from the 1-hour rung. The rungs it had not reached
yet are retired as `superseded` rather than deleted, so the history stays readable.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import case

from .models import Mistake, ReviewEvent, ReviewOutcome, Urgency, utcnow

LADDER: tuple[tuple[str, timedelta], ...] = (
    ("1h", timedelta(hours=1)),
    ("24h", timedelta(hours=24)),
    ("72h", timedelta(hours=72)),
    ("1w", timedelta(weeks=1)),
    ("1mo", timedelta(days=30)),
)

LADDER_LABELS: tuple[str, ...] = tuple(label for label, _ in LADDER)

# Two questions can come due in the same minute. When they do, the more urgent one
# is the one to spend the attention on, so it comes first in the queue. Anything
# with no urgency yet sorts last rather than in the middle.
URGENCY_RANK = case(
    (Mistake.urgency == Urgency.fundamental, 0),
    (Mistake.urgency == Urgency.very_important, 1),
    (Mistake.urgency == Urgency.important, 2),
    else_=3,
)


def build_ladder(mistake_id: str, anchor: datetime, cycle: int = 0) -> list[ReviewEvent]:
    """The five review events for one pass over the ladder, anchored at `anchor`."""
    return [
        ReviewEvent(
            mistake_id=mistake_id,
            cycle=cycle,
            step_index=step,
            interval_label=label,
            due_at=anchor + offset,
        )
        for step, (label, offset) in enumerate(LADDER)
    ]


def open_events(mistake: Mistake) -> list[ReviewEvent]:
    return [e for e in mistake.reviews if e.completed_at is None]


def restart_ladder(mistake: Mistake, anchor: datetime | None = None) -> list[ReviewEvent]:
    """Retire the mistake's remaining rungs and arm a fresh pass from `anchor`."""
    anchor = anchor or utcnow()
    now = utcnow()
    for event in open_events(mistake):
        event.completed_at = now
        event.outcome = ReviewOutcome.superseded

    next_cycle = max((e.cycle for e in mistake.reviews), default=0) + 1
    fresh = build_ladder(mistake.id, anchor, cycle=next_cycle)
    mistake.reviews.extend(fresh)
    return fresh
