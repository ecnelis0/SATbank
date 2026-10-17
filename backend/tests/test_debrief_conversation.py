"""Talking to the debrief: instructions that rewrite and re-tag it, and are kept."""

from __future__ import annotations

from app.analysis import StubAnalyzer
from app.analysis.base import AnalysisFailed, MistakeAnalysis, MistakeInput, PatternTag
from app.analysis.claude import _render
from tests.conftest import MATH_MISTAKE


class Recording(StubAnalyzer):
    """The stub, plus a record of what it was handed and a verdict that follows it."""

    name = "recording"

    def __init__(self) -> None:
        self.seen: list[MistakeInput] = []

    async def analyze(self, mistake: MistakeInput) -> MistakeAnalysis:
        self.seen.append(mistake)
        base = await super().analyze(mistake)
        said = " ".join(t.text for t in mistake.conversation if t.role == "student")
        if "misread" in said.lower():
            return base.model_copy(
                update={
                    "error_type": "misread_question",
                    "headline": "You answered for 3x, not x.",
                    "reply": "Understood - filed as a misread rather than arithmetic.",
                    "patterns": [
                        PatternTag(title="Answered a different quantity", why="3x, not x.")
                    ],
                }
            )
        return base


class Broken(StubAnalyzer):
    name = "broken"

    async def analyze(self, mistake: MistakeInput) -> MistakeAnalysis:
        raise AnalysisFailed("out of credit")


async def _logged(client) -> dict:
    response = await client.post("/mistakes", json=MATH_MISTAKE, params={"analyze": False})
    assert response.status_code == 201
    analysed = await client.post(f"/mistakes/{response.json()['id']}/analyze")
    assert analysed.json()["analysis_status"] == "ready"
    return analysed.json()


async def test_an_instruction_rewrites_and_retags_the_debrief(client, monkeypatch):
    logged = await _logged(client)
    assert logged["error_type"] != "misread_question"
    recording = Recording()
    monkeypatch.setattr("app.services.get_analyzer", lambda: recording)

    response = await client.post(
        f"/mistakes/{logged['id']}/debrief",
        json={"message": "I actually misread it - I solved for 3x and picked that."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["mistake"]["error_type"] == "misread_question"
    assert body["mistake"]["headline"] == "You answered for 3x, not x."
    assert [p["title"] for p in body["mistake"]["patterns"]] == ["Answered a different quantity"]
    assert body["mistake"]["analyzed_by"] == "recording"
    assert [t["role"] for t in body["turns"]] == ["student", "assistant"]
    assert body["turns"][1]["text"].startswith("Understood")


async def test_the_model_is_given_everything_the_debrief_should_weigh(client, monkeypatch):
    logged = await _logged(client)
    recording = Recording()
    monkeypatch.setattr("app.services.get_analyzer", lambda: recording)

    await client.post(f"/mistakes/{logged['id']}/debrief", json={"message": "First thing."})
    await client.post(f"/mistakes/{logged['id']}/debrief", json={"message": "Second thing."})

    handed = recording.seen[-1]
    # The question, the choice, what happened - and the conversation, both sides.
    assert handed.your_answer == MATH_MISTAKE["your_answer"]
    assert handed.student_note == MATH_MISTAKE["student_note"]
    assert [t.role for t in handed.conversation] == ["student", "assistant", "student"]
    assert handed.conversation[-1].text == "Second thing."
    # And the debrief on file, so it is revised rather than started again.
    assert handed.previous_debrief and "Headline:" in handed.previous_debrief

    rendered = _render(handed)
    assert "Second thing." in rendered
    assert "The debrief on file" in rendered
    assert MATH_MISTAKE["student_note"] in rendered


async def test_the_conversation_is_kept_and_comes_back(client):
    logged = await _logged(client)
    await client.post(f"/mistakes/{logged['id']}/debrief", json={"message": "I guessed."})

    turns = (await client.get(f"/mistakes/{logged['id']}/debrief")).json()
    assert turns[0]["role"] == "student"
    assert turns[0]["text"] == "I guessed."
    assert turns[1]["role"] == "assistant"
    assert turns[1]["analyzer"] == "stub"


async def test_a_failed_model_keeps_the_message_and_the_old_debrief(client, monkeypatch):
    logged = await _logged(client)
    monkeypatch.setattr("app.services.get_analyzer", lambda: Broken())

    response = await client.post(
        f"/mistakes/{logged['id']}/debrief", json={"message": "Redo this as a misread."}
    )
    assert response.status_code == 200
    body = response.json()
    assert "out of credit" in body["error"]
    # The student's words survive; nothing was answered, so there is no reply.
    assert [t["role"] for t in body["turns"]] == ["student"]
    # And the debrief they already had is untouched - not marked failed.
    assert body["mistake"]["analysis_status"] == "ready"
    assert body["mistake"]["headline"] == logged["headline"]
    assert body["mistake"]["error_type"] == logged["error_type"]


async def test_a_debrief_with_hand_edits_can_still_be_talked_to(client, monkeypatch):
    """Speaking to it is the request to change it; the edits go to the model."""
    logged = await _logged(client)
    await client.patch(f"/mistakes/{logged['id']}", json={"takeaway": "Divide by 3 last."})
    recording = Recording()
    monkeypatch.setattr("app.services.get_analyzer", lambda: recording)

    response = await client.post(
        f"/mistakes/{logged['id']}/debrief", json={"message": "Keep my takeaway."}
    )
    assert response.json()["error"] is None
    assert "Divide by 3 last." in recording.seen[-1].previous_debrief
    assert "edited parts of this by hand" in recording.seen[-1].previous_debrief


async def test_an_urgency_the_student_chose_survives_the_rewrite(client):
    logged = await _logged(client)
    await client.patch(f"/mistakes/{logged['id']}", json={"urgency": "fundamental"})
    response = await client.post(
        f"/mistakes/{logged['id']}/debrief", json={"message": "This one is minor."}
    )
    assert response.json()["mistake"]["urgency"] == "fundamental"


async def test_a_blank_message_is_refused(client):
    logged = await _logged(client)
    response = await client.post(f"/mistakes/{logged['id']}/debrief", json={"message": ""})
    assert response.status_code == 422
    assert (await client.get(f"/mistakes/{logged['id']}/debrief")).json() == []


async def test_someone_elses_question_cannot_be_talked_to(client):
    logged = await _logged(client)
    response = await client.post(
        f"/mistakes/{logged['id']}/debrief",
        json={"message": "hello"},
        headers={"X-User-Id": "someone-else"},
    )
    assert response.status_code == 404
    response = await client.get(
        f"/mistakes/{logged['id']}/debrief", headers={"X-User-Id": "someone-else"}
    )
    assert response.status_code == 404


async def test_deleting_the_question_deletes_its_conversation(client, session_factory):
    from sqlalchemy import func, select

    from app.models import DebriefTurn

    logged = await _logged(client)
    await client.post(f"/mistakes/{logged['id']}/debrief", json={"message": "I guessed."})
    assert (await client.delete(f"/mistakes/{logged['id']}")).status_code == 204

    async with session_factory() as session:
        left = await session.scalar(select(func.count()).select_from(DebriefTurn))
    assert left == 0


async def test_a_first_debrief_reads_the_question_fresh(client, monkeypatch):
    """No conversation, no previous debrief: an ordinary analysis is unchanged."""
    recording = Recording()
    monkeypatch.setattr("app.services.get_analyzer", lambda: recording)
    logged = await client.post("/mistakes", json=MATH_MISTAKE, params={"analyze": False})
    await client.post(f"/mistakes/{logged.json()['id']}/analyze")
    assert recording.seen[-1].conversation == []
    assert recording.seen[-1].previous_debrief is None
