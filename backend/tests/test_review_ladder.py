"""The ladder is the product. These tests pin its exact shape."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import Mistake, ReviewOutcome
from app.review import LADDER_LABELS, build_ladder, open_events, restart_ladder
from tests.conftest import MATH_MISTAKE

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


# --- one question is one thing to review --------------------------------------
#
# The whole ladder is armed when the question is logged, so a question left alone
# for a month has all five rungs overdue at once. Counting rows made five
# questions read as "12 questions due", and the session dealt the same question
# five times over.


async def _all_rungs_overdue(session_factory, mistake_id: str) -> int:
    """Drag every rung of one question into the past. Returns how many there are."""
    from sqlalchemy import select

    from app.models import ReviewEvent, utcnow

    async with session_factory() as session:
        rungs = list(
            await session.scalars(
                select(ReviewEvent).where(ReviewEvent.mistake_id == mistake_id)
            )
        )
        for index, rung in enumerate(rungs):
            rung.due_at = utcnow() - timedelta(days=40 + index)
        await session.commit()
        return len(rungs)


async def test_a_question_with_every_rung_overdue_counts_once(client, session_factory):
    logged = (await client.post("/mistakes", json=MATH_MISTAKE, params={"analyze": False})).json()
    rungs = await _all_rungs_overdue(session_factory, logged["id"])
    assert rungs > 1, "the ladder should arm more than one rung, or this proves nothing"

    stats = (await client.get("/stats")).json()
    assert stats["due_now"] == 1


async def test_the_due_queue_deals_each_question_once(client, session_factory):
    logged = (await client.post("/mistakes", json=MATH_MISTAKE, params={"analyze": False})).json()
    await _all_rungs_overdue(session_factory, logged["id"])

    due = (await client.get("/reviews/due")).json()
    assert len(due) == 1
    assert due[0]["mistake"]["id"] == logged["id"]


async def test_the_card_offered_is_the_oldest_rung(client, session_factory):
    """The rung that has waited longest is the one to answer; answering a later one
    would leave an older review still hanging."""
    logged = (await client.post("/mistakes", json=MATH_MISTAKE, params={"analyze": False})).json()
    await _all_rungs_overdue(session_factory, logged["id"])

    from sqlalchemy import select

    from app.models import ReviewEvent

    async with session_factory() as session:
        rungs = list(
            await session.scalars(
                select(ReviewEvent).where(ReviewEvent.mistake_id == logged["id"])
            )
        )
    oldest = min(rungs, key=lambda r: r.due_at)

    due = (await client.get("/reviews/due")).json()
    assert due[0]["review"]["id"] == oldest.id


async def test_the_dashboard_and_the_queue_agree(client, session_factory):
    """The number on the dashboard is a promise about how many cards the session
    will deal. They are computed separately, so they have to be checked together."""
    for index in range(3):
        body = dict(MATH_MISTAKE)
        body["question_text"] = f"Question {index}"
        logged = (await client.post("/mistakes", json=body, params={"analyze": False})).json()
        await _all_rungs_overdue(session_factory, logged["id"])

    stats = (await client.get("/stats")).json()
    due = (await client.get("/reviews/due")).json()
    assert stats["due_now"] == 3
    assert len(due) == stats["due_now"]


async def test_the_report_counts_questions_too(client, session_factory):
    logged = (await client.post("/mistakes", json=MATH_MISTAKE, params={"analyze": False})).json()
    await _all_rungs_overdue(session_factory, logged["id"])

    report = (await client.get("/reports", params={"period": "all"})).json()
    assert report["still_due"] == 1


async def test_answering_the_card_does_not_hand_the_same_question_straight_back(
    client, session_factory
):
    """The bug behind the count: five overdue rungs meant answering one left four,
    so the question reappeared in the same session."""
    logged = (await client.post("/mistakes", json=MATH_MISTAKE, params={"analyze": False})).json()
    await _all_rungs_overdue(session_factory, logged["id"])

    due = (await client.get("/reviews/due")).json()
    answered = await client.post(
        f"/reviews/{due[0]['review']['id']}/complete", json={"outcome": "correct"}
    )
    assert answered.status_code == 200

    # It may still be due on an older rung, but it must not be dealt twice over.
    again = (await client.get("/reviews/due")).json()
    assert len(again) <= 1
    assert (await client.get("/stats")).json()["due_now"] <= 1
