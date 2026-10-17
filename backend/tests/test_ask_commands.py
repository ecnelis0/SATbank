"""Commands typed into the ask-about-this-question chat change the debrief."""

from __future__ import annotations

import pytest

from app.analysis.base import AnalysisFailed, MistakeAnalysis, MistakeInput
from app.commands import is_debrief_command
from tests.conftest import MATH_MISTAKE
from tests.test_debrief_conversation import Recording


@pytest.mark.parametrize(
    "text",
    [
        "Consider this in the debrief",
        "consider that in the debrief please",
        "Add that to my debrief",
        "Can you update the debrief with what you just said?",
        "Please rewrite the debrief so it says I misread it",
        "Put this explanation in the debrief",
        "Tag this as a misread",
        "file it under careless arithmetic",
        "Mark this as a time-pressure guess",
    ],
)
def test_instructions_are_recognised(text):
    assert is_debrief_command(text)


@pytest.mark.parametrize(
    "text",
    [
        "What does this debrief mean?",
        "Why is my answer wrong?",
        "Is the debrief correct?",
        "What should I add to the debrief?",
        "How do I do this next time?",
        "The debrief makes sense now, thanks",
        "Explain the trap again",
    ],
)
def test_questions_are_left_as_questions(text):
    """A question taken for a command would rewrite a debrief nobody asked to change."""
    assert not is_debrief_command(text)


async def _logged(client) -> dict:
    response = await client.post("/mistakes", json=MATH_MISTAKE, params={"analyze": False})
    return (await client.post(f"/mistakes/{response.json()['id']}/analyze")).json()


async def test_a_command_in_the_chat_rewrites_the_debrief_with_the_chat(client, monkeypatch):
    logged = await _logged(client)
    recording = Recording()
    monkeypatch.setattr("app.services.get_analyzer", lambda: recording)

    history = [
        {"role": "student", "text": "Did I misread what x was?"},
        {"role": "assistant", "text": "7 is the constant; you misread what x was."},
    ]
    response = await client.post(
        f"/mistakes/{logged['id']}/ask",
        json={"question": "Consider this in the debrief", "history": history},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["debrief_updated"] is True
    assert body["error"] is None
    # The recording analyzer re-files as a misread when the conversation says so,
    # which it only can if the chat's own turns reached it.
    assert body["mistake"]["error_type"] == "misread_question"
    assert body["answer"].startswith("Understood")

    handed = recording.seen[-1].conversation
    assert [t.text for t in handed] == [
        "Did I misread what x was?",
        "7 is the constant; you misread what x was.",
        "Consider this in the debrief",
    ]

    # Kept with the debrief, in order, with its reply - so it can be read again.
    turns = (await client.get(f"/mistakes/{logged['id']}/debrief")).json()
    assert [t["text"] for t in turns][:3] == [t.text for t in handed]
    assert [t["role"] for t in turns] == ["student", "assistant", "student", "assistant"]


async def test_the_button_applies_whatever_the_wording(client, monkeypatch):
    logged = await _logged(client)
    recording = Recording()
    monkeypatch.setattr("app.services.get_analyzer", lambda: recording)

    body = (
        await client.post(
            f"/mistakes/{logged['id']}/ask",
            json={"question": "I misread it, honestly", "apply_to_debrief": True},
        )
    ).json()
    assert body["debrief_updated"] is True
    assert body["mistake"]["error_type"] == "misread_question"


async def test_an_ordinary_question_does_not_touch_the_debrief(client, monkeypatch):
    logged = await _logged(client)

    class Untouchable(Recording):
        async def analyze(self, mistake: MistakeInput) -> MistakeAnalysis:
            raise AssertionError("an ordinary question must not re-run the debrief")

    monkeypatch.setattr("app.services.get_analyzer", lambda: Untouchable())
    body = (
        await client.post(
            f"/mistakes/{logged['id']}/ask", json={"question": "What does this debrief mean?"}
        )
    ).json()
    assert body["debrief_updated"] is False
    assert body["mistake"] is None
    assert (await client.get(f"/mistakes/{logged['id']}/debrief")).json() == []


async def test_a_command_the_model_cannot_answer_keeps_the_words_and_the_debrief(
    client, monkeypatch
):
    logged = await _logged(client)

    class Broken(Recording):
        async def analyze(self, mistake: MistakeInput) -> MistakeAnalysis:
            raise AnalysisFailed("out of credit")

    monkeypatch.setattr("app.services.get_analyzer", lambda: Broken())
    body = (
        await client.post(
            f"/mistakes/{logged['id']}/ask", json={"question": "Add that to my debrief"}
        )
    ).json()
    assert body["debrief_updated"] is False
    assert "out of credit" in body["error"]
    assert body["mistake"]["headline"] == logged["headline"]
    turns = (await client.get(f"/mistakes/{logged['id']}/debrief")).json()
    assert [t["text"] for t in turns] == ["Add that to my debrief"]
