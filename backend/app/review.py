"""The review ladder.

Four rungs: 24 hours, 1 week, 1 month, 3 months. Identical for every card - this
is deliberately not SM-2/Anki, where an ease factor stretches the gaps per card.

One rung is scheduled at a time, measured from the moment the last one was
answered:

* **Right** - the next rung is scheduled. Passing the 3-month rung finishes the
  question.
* **Wrong** - the *same* rung again, with the same wait. Missing the 1-week review
  means another 1-week review, and so on until it is right; only then does the
  question move up. A miss does not send it back to the start.
* **Skipped** - the same rung, back tomorrow. Waiting the rung's whole interval
  again would turn one skip into three months' silence at the top of the ladder.

Each answered rung stays on the record. `cycle` counts attempts at a rung: 0 for
the first, 1 after one miss, and so on.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import case

from .models import Mistake, ReviewEvent, ReviewOutcome, Urgency, utcnow

LADDER: tuple[tuple[str, timedelta], ...] = (
    ("24h", timedelta(hours=24)),
    ("1w", timedelta(weeks=1)),
    ("1mo", timedelta(days=30)),
    ("3mo", timedelta(days=90)),
)

LADDER_LABELS: tuple[str, ...] = tuple(label for label, _ in LADDER)

# A skipped review comes back after this, whatever its rung.
SKIP_DELAY = timedelta(hours=24)

# Two questions can come due in the same minute. When they do, the more urgent one
# is the one to spend the attention on, so it comes first in the queue. Anything
# with no urgency yet sorts last rather than in the middle.
URGENCY_RANK = case(
    (Mistake.urgency == Urgency.fundamental, 0),
    (Mistake.urgency == Urgency.very_important, 1),
    (Mistake.urgency == Urgency.important, 2),
    else_=3,
)


def first_rung(mistake_id: str, anchor: datetime) -> ReviewEvent:
    """The 24-hour review, armed the moment a question is logged."""
    label, wait = LADDER[0]
    return ReviewEvent(
        mistake_id=mistake_id, cycle=0, step_index=0, interval_label=label, due_at=anchor + wait
    )


def next_rung(event: ReviewEvent, outcome: ReviewOutcome, now: datetime) -> ReviewEvent | None:
    """What to schedule after `event` was answered with `outcome`, or None when
    that was the last rung passed."""
    step = event.step_index
    if outcome is ReviewOutcome.correct:
        step += 1
        if step >= len(LADDER):
            return None
        label, wait = LADDER[step]
        cycle = 0
    elif outcome is ReviewOutcome.wrong:
        label, wait = LADDER[step]
        cycle = event.cycle + 1
    else:  # skipped
        label, _ = LADDER[step]
        wait, cycle = SKIP_DELAY, event.cycle
    return ReviewEvent(
        mistake_id=event.mistake_id,
        cycle=cycle,
        step_index=step,
        interval_label=label,
        due_at=now + wait,
    )


def open_events(mistake: Mistake) -> list[ReviewEvent]:
    return [e for e in mistake.reviews if e.completed_at is None]


def answer(mistake: Mistake, event: ReviewEvent, outcome: ReviewOutcome) -> ReviewEvent | None:
    """Record the answer and schedule what comes next. Returns the new rung."""
    now = utcnow()
    event.completed_at = now
    event.outcome = outcome
    following = next_rung(event, outcome, now)
    if following is not None:
        mistake.reviews.append(following)
    return following
