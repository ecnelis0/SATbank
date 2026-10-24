"""The ladder is the product. These tests pin its exact shape."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import Mistake, ReviewOutcome
from app.review import LADDER_LABELS, SKIP_DELAY, answer, first_rung, next_rung, open_events
from tests.conftest import MATH_MISTAKE

ANCHOR = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 3, 9, 18, 30, tzinfo=UTC)


def test_ladder_is_the_four_intervals_the_product_promises():
    assert LADDER_LABELS == ("24h", "1w", "1mo", "3mo")


def test_a_new_question_has_only_its_24_hour_review():
    rung = first_rung("m1", ANCHOR)
    assert (rung.interval_label, rung.step_index, rung.cycle) == ("24h", 0, 0)
    assert rung.due_at == ANCHOR + timedelta(hours=24)


def _rung(label: str, step: int, cycle: int = 0):
    rung = first_rung("m1", ANCHOR)
    rung.interval_label, rung.step_index, rung.cycle = label, step, cycle
    return rung


def test_right_moves_up_a_rung_measured_from_when_it_was_answered():
    following = next_rung(_rung("24h", 0), ReviewOutcome.correct, LATER)
    assert (following.interval_label, following.step_index, following.cycle) == ("1w", 1, 0)
    assert following.due_at == LATER + timedelta(weeks=1)


def test_wrong_repeats_the_same_rung_with_the_same_wait():
    """Missed the 1-week review: another 1-week review, not back to the start."""
    following = next_rung(_rung("1w", 1), ReviewOutcome.wrong, LATER)
    assert (following.interval_label, following.step_index) == ("1w", 1)
    assert following.due_at == LATER + timedelta(weeks=1)
    assert following.cycle == 1


def test_every_miss_repeats_until_it_is_right_and_only_then_moves_on():
    rung = _rung("1mo", 2)
    for attempt in range(1, 4):
        rung = next_rung(rung, ReviewOutcome.wrong, LATER)
        assert (rung.interval_label, rung.cycle) == ("1mo", attempt)
        assert rung.due_at == LATER + timedelta(days=30)
    rung = next_rung(rung, ReviewOutcome.correct, LATER)
    assert (rung.interval_label, rung.cycle) == ("3mo", 0)
    assert rung.due_at == LATER + timedelta(days=90)


def test_passing_the_3_month_review_finishes_the_question():
    assert next_rung(_rung("3mo", 3), ReviewOutcome.correct, LATER) is None


def test_missing_the_3_month_review_repeats_it():
    following = next_rung(_rung("3mo", 3), ReviewOutcome.wrong, LATER)
    assert following.interval_label == "3mo"
    assert following.due_at == LATER + timedelta(days=90)


def test_a_skip_keeps_the_rung_and_comes_back_tomorrow():
    """Not the rung's whole wait: one skip at 3 months must not mean 3 months' silence."""
    following = next_rung(_rung("3mo", 3, cycle=2), ReviewOutcome.skipped, LATER)
    assert (following.interval_label, following.cycle) == ("3mo", 2)
    assert following.due_at == LATER + SKIP_DELAY


def test_answering_keeps_one_open_rung_and_the_history():
    mistake = Mistake(
        id="m1", user_id="local", section="math", question_text="q",
        your_answer="7", correct_answer="5",
    )
    mistake.reviews.append(first_rung("m1", ANCHOR))
    first = mistake.reviews[0]
    answer(mistake, first, ReviewOutcome.wrong)
    second = open_events(mistake)[0]
    answer(mistake, second, ReviewOutcome.correct)

    assert [e.outcome for e in mistake.reviews] == [
        ReviewOutcome.wrong, ReviewOutcome.correct, None,
    ]
    assert [e.interval_label for e in open_events(mistake)] == ["1w"]


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
        # The ladder keeps one open rung now, but a bank migrated from the old
        # five-rung ladder can hold several - the queue must still deal once.
        for step, label in ((1, "1w"), (2, "1mo")):
            extra = ReviewEvent(
                mistake_id=mistake_id, cycle=0, step_index=step,
                interval_label=label, due_at=utcnow(),
            )
            session.add(extra)
            rungs.append(extra)
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
