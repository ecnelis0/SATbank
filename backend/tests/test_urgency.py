"""Urgency: how badly a question needs revisiting, and what that changes."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import Mistake, ReviewEvent
from tests.conftest import MATH_MISTAKE, VERBAL_MISTAKE


async def _backdate(session_factory, mistake_id: str, delta: timedelta) -> None:
    async with session_factory() as session:
        mistake = await session.get(Mistake, mistake_id)
        mistake.created_at = mistake.created_at - delta
        events = await session.scalars(
            select(ReviewEvent).where(ReviewEvent.mistake_id == mistake_id)
        )
        for event in events:
            event.due_at = event.due_at - delta
        await session.commit()


async def _set_urgency(client, mistake_id: str, urgency: str) -> None:
    response = await client.patch(f"/mistakes/{mistake_id}", json={"urgency": urgency})
    assert response.status_code == 200


async def test_the_analyzer_assigns_an_urgency(client):
    body = (await client.post("/mistakes", json=MATH_MISTAKE)).json()

    stored = (await client.get(f"/mistakes/{body['id']}")).json()
    assert stored["urgency"] in {"fundamental", "very_important", "important"}


async def test_a_concept_gap_is_fundamental_but_a_slip_is_not(client):
    """The stub's rule, and the shape the real prompt asks Claude for: judge the gap."""
    slip = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    gap = (await client.post("/mistakes", json=VERBAL_MISTAKE)).json()["id"]

    slip_body = (await client.get(f"/mistakes/{slip}")).json()
    gap_body = (await client.get(f"/mistakes/{gap}")).json()

    assert slip_body["error_type"] == "careless_arithmetic"
    assert slip_body["urgency"] == "important"
    assert gap_body["error_type"] == "evidence_misread"
    assert gap_body["urgency"] == "very_important"


async def test_urgency_is_editable_like_everything_else(client):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]

    updated = (
        await client.patch(f"/mistakes/{mistake_id}", json={"urgency": "fundamental"})
    ).json()

    assert updated["urgency"] == "fundamental"
    # It is part of the analysis, so overriding it counts as editing the analysis.
    assert updated["analysis_edited_at"] is not None


@pytest.mark.parametrize("bad", ["urgent", "critical", "IMPORTANT"])
async def test_urgency_is_a_closed_vocabulary(client, bad):
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]

    response = await client.patch(f"/mistakes/{mistake_id}", json={"urgency": bad})

    assert response.status_code == 422


async def test_the_bank_filters_by_urgency(client):
    first = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    await client.post("/mistakes", json=VERBAL_MISTAKE)
    await _set_urgency(client, first, "fundamental")

    found = (await client.get("/mistakes", params={"urgency": "fundamental"})).json()

    assert [m["id"] for m in found] == [first]


async def test_stats_counts_the_urgencies(client):
    first = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    await client.post("/mistakes", json=VERBAL_MISTAKE)
    await _set_urgency(client, first, "fundamental")

    stats = (await client.get("/stats")).json()

    assert {"key": "fundamental", "count": 1} in stats["by_urgency"]
    assert sum(s["count"] for s in stats["by_urgency"]) == 2


async def test_the_review_queue_puts_the_most_urgent_question_first(client, session_factory):
    """Both are due; the one that matters more should be the one on screen."""
    older = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    newer = (await client.post("/mistakes", json=VERBAL_MISTAKE)).json()["id"]

    # The *older* question is the less urgent one, so date order and urgency order
    # disagree - which is the only case that can tell the two apart.
    await _set_urgency(client, older, "important")
    await _set_urgency(client, newer, "fundamental")
    await _backdate(session_factory, older, timedelta(hours=4))
    await _backdate(session_factory, newer, timedelta(hours=2))

    due = (await client.get("/reviews/due")).json()

    assert [d["mistake"]["id"] for d in due] == [newer, older]
    assert [d["mistake"]["urgency"] for d in due] == ["fundamental", "important"]


async def test_a_question_with_no_urgency_yet_sorts_last_not_in_the_middle(client, session_factory):
    rated = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    unrated = (
        await client.post("/mistakes", params={"analyze": "false"}, json=VERBAL_MISTAKE)
    ).json()["id"]

    await _set_urgency(client, rated, "important")
    # The unrated one is older, so date order alone would put it first.
    await _backdate(session_factory, unrated, timedelta(hours=4))
    await _backdate(session_factory, rated, timedelta(hours=2))

    due = (await client.get("/reviews/due")).json()

    assert (await client.get(f"/mistakes/{unrated}")).json()["urgency"] is None
    assert [d["mistake"]["id"] for d in due] == [rated, unrated]


async def test_upcoming_reviews_stay_in_date_order(client):
    """Urgency decides what to do now; it must not reorder the calendar."""
    urgent = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    await _set_urgency(client, urgent, "fundamental")

    upcoming = (await client.get("/reviews/upcoming")).json()
    dues = [u["review"]["due_at"] for u in upcoming]

    assert dues == sorted(dues)
    assert [u["review"]["interval_label"] for u in upcoming][:5] == [
        "1h",
        "24h",
        "72h",
        "1w",
        "1mo",
    ]
