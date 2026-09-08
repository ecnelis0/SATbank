"""What the student keeps getting wrong, as opposed to what they got wrong once.

"Which questions have I consistently been getting wrong in the past month" is a
question about repetition. Listing rows cannot answer it, and a model asked to
count a list by eye will approximate - so the repetition is counted here.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.models import Mistake, ReviewEvent
from tests.conftest import MATH_MISTAKE, VERBAL_MISTAKE


async def _log(client, payload, **overrides):
    mistake_id = (await client.post("/mistakes", json=payload)).json()["id"]
    if overrides:
        assert (await client.patch(f"/mistakes/{mistake_id}", json=overrides)).status_code == 200
    return mistake_id


async def _age(session_factory, mistake_id: str, days: float) -> None:
    async with session_factory() as session:
        mistake = await session.get(Mistake, mistake_id)
        mistake.created_at = mistake.created_at - timedelta(days=days)
        events = await session.scalars(
            select(ReviewEvent).where(ReviewEvent.mistake_id == mistake_id)
        )
        for event in events:
            event.due_at = event.due_at - timedelta(days=days)
        await session.commit()


async def _miss_it_again(client, session_factory, mistake_id: str, times: int = 1) -> None:
    """Answer this question's due review wrong, `times` times over."""
    for _ in range(times):
        await _age(session_factory, mistake_id, days=1)
        due = (await client.get("/reviews/due")).json()
        review = next(d["review"] for d in due if d["mistake"]["id"] == mistake_id)
        response = await client.post(f"/reviews/{review['id']}/complete", json={"outcome": "wrong"})
        assert response.status_code == 200


async def test_a_question_missed_again_is_counted(client, session_factory):
    mistake_id = await _log(client, MATH_MISTAKE, topic="inverse trig")
    await _miss_it_again(client, session_factory, mistake_id, times=2)

    body = (await client.post("/ask", json={"question": "everything"})).json()

    assert "2 time(s) in total" in body["answer"]


async def test_a_question_answered_correctly_is_not_a_pattern(client, session_factory):
    mistake_id = await _log(client, MATH_MISTAKE)
    await _age(session_factory, mistake_id, days=1)
    due = (await client.get("/reviews/due")).json()
    await client.post(f"/reviews/{due[0]['review']['id']}/complete", json={"outcome": "correct"})

    body = (await client.post("/ask", json={"question": "everything"})).json()

    assert "Nothing in this set has been missed again" in body["answer"]


async def test_the_topic_you_keep_missing_is_named(client, session_factory):
    """The student's own example: inverse trig, wrong again and again."""
    trig = await _log(client, MATH_MISTAKE, topic="inverse trig")
    other = await _log(client, VERBAL_MISTAKE, topic="command of evidence")
    await _miss_it_again(client, session_factory, trig, times=3)
    await _miss_it_again(client, session_factory, other, times=1)

    body = (
        await client.post(
            "/ask",
            json={"question": "which questions have I consistently been getting wrong"},
        )
    ).json()

    # Named, with a number, and ordered so the worst comes first.
    assert "inverse trig (3 repeat misses)" in body["answer"]
    assert body["answer"].index("inverse trig") < body["answer"].index("command of evidence")


async def test_repetition_beats_volume(client, session_factory):
    """Ten questions logged once each is not a pattern; three repeats is."""
    for _ in range(4):
        await _log(client, VERBAL_MISTAKE, topic="command of evidence")
    trig = await _log(client, MATH_MISTAKE, topic="inverse trig")
    await _miss_it_again(client, session_factory, trig, times=2)

    body = (await client.post("/ask", json={"question": "what do I keep getting wrong"})).json()

    assert "inverse trig" in body["answer"]
    assert "command of evidence" not in body["answer"]


async def test_a_concept_you_keep_missing_is_named(client, session_factory):
    mistake_id = await _log(client, MATH_MISTAKE)
    concept = (await client.post("/concepts", json={"title": "Inverse trig needs a domain"})).json()
    await client.post(f"/concepts/{concept['id']}/questions/{mistake_id}")
    await _miss_it_again(client, session_factory, mistake_id, times=2)

    body = (await client.post("/ask", json={"question": "what keeps coming back"})).json()

    assert "Inverse trig needs a domain (2 repeat misses)" in body["answer"]


async def test_the_period_is_respected(client, session_factory):
    """ "in the past month" must exclude what happened before it."""
    recent = await _log(client, MATH_MISTAKE, topic="inverse trig")
    old = await _log(client, VERBAL_MISTAKE, topic="command of evidence")
    await _miss_it_again(client, session_factory, recent, times=2)
    await _miss_it_again(client, session_factory, old, times=2)
    await _age(session_factory, old, days=120)

    body = (
        await client.post(
            "/ask",
            json={"question": "what have I consistently got wrong in the past month"},
        )
    ).json()

    assert "logged since" in body["filter_description"]
    assert [m["id"] for m in body["mistakes"]] == [recent]
    assert "inverse trig" in body["answer"]
    assert "command of evidence" not in body["answer"]


async def test_the_worst_offenders_are_quoted(client, session_factory):
    mistake_id = await _log(client, MATH_MISTAKE)
    await _miss_it_again(client, session_factory, mistake_id, times=2)

    body = (await client.post("/ask", json={"question": "what do I keep missing"})).json()

    assert MATH_MISTAKE["question_text"][:40] in body["answer"]


async def test_bookkeeping_from_a_restart_is_not_counted_as_a_miss(client, session_factory):
    """A miss retires the rungs it never reached; those are not extra misses."""
    mistake_id = await _log(client, MATH_MISTAKE)
    await _miss_it_again(client, session_factory, mistake_id, times=1)

    stored = (await client.get(f"/mistakes/{mistake_id}")).json()
    superseded = [r for r in stored["reviews"] if r["outcome"] == "superseded"]
    assert len(superseded) == 4  # the rungs the restart retired

    body = (await client.post("/ask", json={"question": "everything"})).json()
    assert "1 time(s) in total" in body["answer"]
