from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Mistake, ReviewEvent, ReviewOutcome
from tests.conftest import MATH_MISTAKE, VERBAL_MISTAKE


async def _backdate(session_factory, mistake_id: str, delta: timedelta) -> None:
    """Move a mistake and its whole ladder back in time, as if it were logged then."""
    async with session_factory() as session:
        mistake = await session.get(Mistake, mistake_id)
        mistake.created_at = mistake.created_at - delta
        events = await session.scalars(
            select(ReviewEvent).where(ReviewEvent.mistake_id == mistake_id)
        )
        for event in events:
            event.due_at = event.due_at - delta
        await session.commit()


async def test_logging_a_mistake_arms_the_ladder_and_runs_the_analyzer(client):
    response = await client.post("/mistakes", json=MATH_MISTAKE)
    assert response.status_code == 201, response.text
    body = response.json()

    assert [r["interval_label"] for r in body["reviews"]] == ["1h", "24h", "72h", "1w", "1mo"]
    assert all(r["completed_at"] is None for r in body["reviews"])

    # The background analysis has run by the time the response cycle completes.
    stored = (await client.get(f"/mistakes/{body['id']}")).json()
    assert stored["analysis_status"] == "ready"
    assert stored["analyzed_by"] == "stub"
    assert stored["error_type"] is not None
    assert stored["why_wrong"]
    assert stored["takeaway"]


async def test_nothing_is_due_in_the_first_hour(client):
    await client.post("/mistakes", json=MATH_MISTAKE)

    assert (await client.get("/reviews/due")).json() == []
    upcoming = (await client.get("/reviews/upcoming")).json()
    assert [u["review"]["interval_label"] for u in upcoming] == ["1h", "24h", "72h", "1w", "1mo"]


async def test_the_one_hour_rung_comes_due_and_only_that_rung(client, session_factory):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    await _backdate(session_factory, mistake_id, timedelta(hours=2))

    due = (await client.get("/reviews/due")).json()
    assert [d["review"]["interval_label"] for d in due] == ["1h"]
    # The question travels with the review, so a session needs one request.
    assert due[0]["mistake"]["question_text"] == MATH_MISTAKE["question_text"]


async def test_getting_it_right_leaves_the_rest_of_the_ladder_alone(client, session_factory):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    await _backdate(session_factory, mistake_id, timedelta(hours=2))
    review_id = (await client.get("/reviews/due")).json()[0]["review"]["id"]

    result = (
        await client.post(f"/reviews/{review_id}/complete", json={"outcome": "correct"})
    ).json()

    assert result["ladder_restarted"] is False
    assert result["review"]["outcome"] == "correct"

    mistake = (await client.get(f"/mistakes/{mistake_id}")).json()
    open_labels = [r["interval_label"] for r in mistake["reviews"] if r["completed_at"] is None]
    assert open_labels == ["24h", "72h", "1w", "1mo"]
    assert len(mistake["reviews"]) == 5


async def test_getting_it_wrong_restarts_the_ladder_from_one_hour(client, session_factory):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    await _backdate(session_factory, mistake_id, timedelta(hours=2))
    review_id = (await client.get("/reviews/due")).json()[0]["review"]["id"]

    result = (await client.post(f"/reviews/{review_id}/complete", json={"outcome": "wrong"})).json()

    assert result["ladder_restarted"] is True
    next_due = datetime.fromisoformat(result["next_due_at"])
    assert timedelta(minutes=55) < next_due - datetime.now(UTC) < timedelta(minutes=65)

    mistake = (await client.get(f"/mistakes/{mistake_id}")).json()
    open_rungs = [r for r in mistake["reviews"] if r["completed_at"] is None]
    assert [r["interval_label"] for r in open_rungs] == ["1h", "24h", "72h", "1w", "1mo"]
    assert all(r["cycle"] == 1 for r in open_rungs)
    # Nothing is due right now: the restarted ladder starts an hour out.
    assert (await client.get("/reviews/due")).json() == []


async def test_skipping_does_not_restart_the_ladder(client, session_factory):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    await _backdate(session_factory, mistake_id, timedelta(hours=2))
    review_id = (await client.get("/reviews/due")).json()[0]["review"]["id"]

    result = (
        await client.post(f"/reviews/{review_id}/complete", json={"outcome": "skipped"})
    ).json()
    assert result["ladder_restarted"] is False


async def test_a_review_cannot_be_completed_twice(client, session_factory):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    await _backdate(session_factory, mistake_id, timedelta(hours=2))
    review_id = (await client.get("/reviews/due")).json()[0]["review"]["id"]

    first = await client.post(f"/reviews/{review_id}/complete", json={"outcome": "correct"})
    second = await client.post(f"/reviews/{review_id}/complete", json={"outcome": "wrong"})

    assert first.status_code == 200
    assert second.status_code == 409


async def test_superseded_is_not_a_student_outcome(client, session_factory):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    await _backdate(session_factory, mistake_id, timedelta(hours=2))
    review_id = (await client.get("/reviews/due")).json()[0]["review"]["id"]

    response = await client.post(
        f"/reviews/{review_id}/complete", json={"outcome": ReviewOutcome.superseded.value}
    )
    assert response.status_code == 422


async def test_one_students_bank_is_invisible_to_another(client):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    other = {"X-User-Id": "someone-else"}

    assert (await client.get(f"/mistakes/{mistake_id}", headers=other)).status_code == 404
    assert (await client.get("/mistakes", headers=other)).json() == []
    assert (await client.get("/reviews/upcoming", headers=other)).json() == []


async def test_another_student_cannot_complete_your_review(client, session_factory):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    await _backdate(session_factory, mistake_id, timedelta(hours=2))
    review_id = (await client.get("/reviews/due")).json()[0]["review"]["id"]

    response = await client.post(
        f"/reviews/{review_id}/complete",
        json={"outcome": "correct"},
        headers={"X-User-Id": "someone-else"},
    )
    assert response.status_code == 404


async def test_the_bank_filters_by_the_slots_the_ai_assigned(client):
    await client.post("/mistakes", json=MATH_MISTAKE)
    await client.post("/mistakes", json=VERBAL_MISTAKE)

    everything = (await client.get("/mistakes")).json()
    assert len(everything) == 2

    math_only = (await client.get("/mistakes", params={"section": "math"})).json()
    assert [m["section"] for m in math_only] == ["math"]

    slot = everything[0]["error_type"]
    by_slot = (await client.get("/mistakes", params={"error_type": slot})).json()
    assert by_slot and all(m["error_type"] == slot for m in by_slot)

    found = (await client.get("/mistakes", params={"q": "3x + 7"})).json()
    assert len(found) == 1


async def test_stats_counts_the_slots(client, session_factory):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    await client.post("/mistakes", json=VERBAL_MISTAKE)
    await _backdate(session_factory, mistake_id, timedelta(hours=2))

    stats = (await client.get("/stats")).json()

    assert stats["total_mistakes"] == 2
    assert stats["due_now"] == 1
    assert stats["reviews_completed"] == 0
    assert sum(s["count"] for s in stats["by_error_type"]) == 2
    assert {s["key"] for s in stats["by_section"]} == {"math", "reading_writing"}


async def test_superseded_rungs_are_not_counted_as_reviews_the_student_did(client, session_factory):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    await _backdate(session_factory, mistake_id, timedelta(hours=2))
    review_id = (await client.get("/reviews/due")).json()[0]["review"]["id"]
    await client.post(f"/reviews/{review_id}/complete", json={"outcome": "wrong"})

    stats = (await client.get("/stats")).json()
    # One answered review, plus four rungs the restart retired.
    assert stats["reviews_completed"] == 1


async def test_deleting_a_mistake_takes_its_ladder_with_it(client):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]

    assert (await client.delete(f"/mistakes/{mistake_id}")).status_code == 204
    assert (await client.get(f"/mistakes/{mistake_id}")).status_code == 404
    assert (await client.get("/reviews/upcoming")).json() == []


@pytest.mark.parametrize(
    "payload",
    [
        {**MATH_MISTAKE, "question_text": "   "},
        {**MATH_MISTAKE, "your_answer": ""},
        {**MATH_MISTAKE, "section": "essay"},
    ],
)
async def test_a_mistake_without_the_essentials_is_rejected(client, payload):
    assert (await client.post("/mistakes", json=payload)).status_code == 422


async def test_timestamps_survive_the_round_trip_as_utc(client, session_factory):
    """SQLite stores no offset; every timestamp must still come back UTC-aware.

    Without this, a completion whose ladder restarts compares a freshly built aware
    due date against a naive one loaded from the database and raises TypeError - and
    every timestamp the frontend receives is missing its offset.
    """
    from app.models import Mistake

    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]

    async with session_factory() as session:
        stored = await session.get(Mistake, mistake_id)
        assert stored.created_at.tzinfo is not None
        assert stored.created_at.utcoffset() == timedelta(0)

    body = (await client.get(f"/mistakes/{mistake_id}")).json()
    assert body["created_at"].endswith("Z") or body["created_at"].endswith("+00:00")
    assert all(datetime.fromisoformat(r["due_at"]).tzinfo is not None for r in body["reviews"])


async def test_completing_correctly_reports_the_next_rung_as_an_aware_timestamp(
    client, session_factory
):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    await _backdate(session_factory, mistake_id, timedelta(hours=2))
    review_id = (await client.get("/reviews/due")).json()[0]["review"]["id"]

    result = (
        await client.post(f"/reviews/{review_id}/complete", json={"outcome": "correct"})
    ).json()

    next_due = datetime.fromisoformat(result["next_due_at"])
    assert next_due.tzinfo is not None
    # The 24-hour rung, measured from a mistake logged two hours ago.
    assert timedelta(hours=21) < next_due - datetime.now(UTC) < timedelta(hours=23)
