"""Asking the AI about one question, after its debrief."""

from __future__ import annotations

from app.analysis import get_analyzer
from app.analysis.base import Turn
from app.routers.mistakes import render_for_discussion
from tests.conftest import MATH_MISTAKE


async def _logged(client):
    response = await client.post("/mistakes", json=MATH_MISTAKE, params={"analyze": True})
    assert response.status_code == 201
    return response.json()


async def test_a_follow_up_gets_an_answer(client):
    logged = await _logged(client)
    response = await client.post(
        f"/mistakes/{logged['id']}/ask",
        json={"question": "What does takeaway mean here?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert body["analyzer"] == "stub"


async def test_the_offline_reader_says_it_cannot_tutor_rather_than_inventing(client):
    """A plausible non-answer about the student's own mistake is the worst thing
    the stub could produce — they would revise from it."""
    logged = await _logged(client)
    response = await client.post(
        f"/mistakes/{logged['id']}/ask", json={"question": "Why is my answer wrong?"}
    )
    assert "cannot answer follow-up questions" in response.json()["answer"]
    # `analyzer_ready` is about configuration, and the stub needs none — it is
    # the provider *name* that tells the UI there is no model behind this.
    assert response.json()["analyzer"] == "stub"


async def test_the_history_travels_with_the_question(client):
    logged = await _logged(client)
    response = await client.post(
        f"/mistakes/{logged['id']}/ask",
        json={
            "question": "So what should I do next time?",
            "history": [
                {"role": "student", "text": "Why is this wrong?"},
                {"role": "assistant", "text": "You stopped a step early."},
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["answer"]


async def test_a_blank_question_is_refused(client):
    logged = await _logged(client)
    response = await client.post(f"/mistakes/{logged['id']}/ask", json={"question": ""})
    assert response.status_code == 422


async def test_you_cannot_ask_about_someone_elses_question(client):
    logged = await _logged(client)
    response = await client.post(
        f"/mistakes/{logged['id']}/ask",
        json={"question": "What does this mean?"},
        headers={"X-User-Id": "someone-else"},
    )
    assert response.status_code == 404


async def test_a_failing_analyzer_leaves_the_debrief_alone(client, monkeypatch):
    """The follow-up is a bonus; losing it must not look like the page breaking."""
    logged = await _logged(client)

    class Broken:
        name = "broken"

        async def discuss(self, context, conversation):
            raise RuntimeError("no model today")

    monkeypatch.setattr("app.routers.mistakes.get_analyzer", lambda: Broken())

    response = await client.post(
        f"/mistakes/{logged['id']}/ask", json={"question": "What does trap mean?"}
    )
    assert response.status_code == 200
    assert "could not be answered" in response.json()["answer"]
    assert "no model today" in response.json()["error"]


# --- what the tutor is told ---------------------------------------------------


async def test_the_context_carries_the_question_and_its_debrief(client, session_factory):
    from app.models import Mistake

    logged = await _logged(client)
    async with session_factory() as session:
        mistake = await session.get(Mistake, logged["id"])
        rendered = render_for_discussion(mistake)

    assert MATH_MISTAKE["question_text"] in rendered
    # Their own words about what happened are the most useful line in it.
    assert MATH_MISTAKE["student_note"] in rendered
    assert "The student answered: 7" in rendered
    assert "The correct answer: 5" in rendered
    # The debrief the stub wrote, so a question about it can be answered.
    assert "Takeaway:" in rendered


async def test_the_context_labels_choices_the_way_the_app_shows_them(client, session_factory):
    from app.models import Mistake

    logged = await _logged(client)
    async with session_factory() as session:
        mistake = await session.get(Mistake, logged["id"])
        rendered = render_for_discussion(mistake)

    # "Is it B or C?" is unanswerable unless the labels line up with the screen.
    assert "A) 3" in rendered
    assert "D) 15" in rendered


async def test_the_context_leaves_out_what_was_never_filled_in(client, session_factory):
    from app.models import Mistake

    body = {k: v for k, v in MATH_MISTAKE.items() if k not in ("source", "student_note")}
    logged = (await client.post("/mistakes", json=body, params={"analyze": False})).json()
    async with session_factory() as session:
        mistake = await session.get(Mistake, logged["id"])
        rendered = render_for_discussion(mistake)

    assert "Source:" not in rendered
    assert "What the student said happened:" not in rendered


async def test_the_stub_keeps_its_shape_for_a_turn_list():
    analyzer = get_analyzer()
    answer = await analyzer.discuss(
        "Question: something\nTakeaway: do the last step",
        [Turn(role="student", text="what is the takeaway?")],
    )
    assert "Takeaway: do the last step" in answer
