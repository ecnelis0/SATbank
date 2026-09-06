"""The ladder is the product. These tests pin its exact shape."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import Mistake, ReviewOutcome
from app.review import LADDER_LABELS, build_ladder, open_events, restart_ladder

ANCHOR = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)


def test_ladder_is_the_five_intervals_the_product_promises():
    assert LADDER_LABELS == ("1h", "24h", "72h", "1w", "1mo")


def test_build_ladder_offsets_are_absolute_from_the_anchor():
    events = build_ladder("m1", ANCHOR)

    assert [e.due_at - ANCHOR for e in events] == [
        timedelta(hours=1),
        timedelta(hours=24),
        timedelta(hours=72),
        timedelta(days=7),
        timedelta(days=30),
    ]
    assert [e.step_index for e in events] == [0, 1, 2, 3, 4]
    assert all(e.cycle == 0 for e in events)
    assert all(e.mistake_id == "m1" for e in events)


def test_two_mistakes_logged_at_the_same_moment_get_identical_schedules():
    """No per-card ease factor: the gaps never differ between cards."""
    a = build_ladder("a", ANCHOR)
    b = build_ladder("b", ANCHOR)

    assert [e.due_at for e in a] == [e.due_at for e in b]


def _mistake_with_ladder() -> Mistake:
    mistake = Mistake(
        id="m1",
        user_id="local",
        section="math",
        question_text="q",
        your_answer="7",
        correct_answer="5",
    )
    mistake.reviews.extend(build_ladder("m1", ANCHOR))
    return mistake


def test_restart_supersedes_open_rungs_and_arms_a_new_cycle():
    mistake = _mistake_with_ladder()
    # The student sat the 1-hour review and got it wrong.
    first = mistake.reviews[0]
    first.completed_at = datetime(2026, 3, 1, 10, 5, tzinfo=UTC)
    first.outcome = ReviewOutcome.wrong

    restart_at = datetime(2026, 3, 1, 10, 5, tzinfo=UTC)
    fresh = restart_ladder(mistake, anchor=restart_at)

    # The four rungs it never reached are retired, not deleted.
    retired = [e for e in mistake.reviews if e.cycle == 0 and e is not first]
    assert len(retired) == 4
    assert all(e.outcome == ReviewOutcome.superseded for e in retired)
    assert all(e.completed_at is not None for e in retired)

    # The student's own answer is untouched.
    assert first.outcome == ReviewOutcome.wrong

    # And the ladder starts again, from the top, from the restart moment.
    assert len(fresh) == 5
    assert all(e.cycle == 1 for e in fresh)
    assert [e.interval_label for e in fresh] == list(LADDER_LABELS)
    assert fresh[0].due_at == restart_at + timedelta(hours=1)
    assert open_events(mistake) == fresh


def test_repeated_misses_keep_incrementing_the_cycle():
    mistake = _mistake_with_ladder()
    restart_ladder(mistake, anchor=ANCHOR)
    restart_ladder(mistake, anchor=ANCHOR)

    assert max(e.cycle for e in mistake.reviews) == 2
    assert len(open_events(mistake)) == 5
    # Nothing is lost: three cycles of five rungs are all still on the record.
    assert len(mistake.reviews) == 15
