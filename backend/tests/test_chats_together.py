"""The two chats on a question are one conversation: each knows what the other said."""

from __future__ import annotations

from app.analysis import StubAnalyzer
from app.analysis.base import Turn
from tests.conftest import MATH_MISTAKE
from tests.test_debrief_conversation import Recording


class Listening(StubAnalyzer):
    """Records what the ask-about-this-question tutor was shown."""

    def __init__(self) -> None:
        self.context = ""
        self.conversation: list[Turn] = []

    async def discuss(self, context: str, conversation: list[Turn]) -> str:
        self.context, self.conversation = context, conversation
        return "Answered."


async def _logged(client) -> str:
    response = await client.post("/mistakes", json=MATH_MISTAKE, params={"analyze": False})
    mistake_id = response.json()["id"]
    await client.post(f"/mistakes/{mistake_id}/analyze")
    return mistake_id


async def test_the_ask_chat_knows_what_the_debrief_was_told(client, monkeypatch):
    mistake_id = await _logged(client)
    await client.post(f"/mistakes/{mistake_id}/debrief", json={"message": "I misread it."})

    listening = Listening()
    monkeypatch.setattr("app.routers.mistakes.get_analyzer", lambda: listening)
    await client.post(f"/mistakes/{mistake_id}/ask", json={"question": "Why was that wrong?"})

    assert "What the student and the debrief have already said" in listening.context
    assert "Student: I misread it." in listening.context
    # And the debrief's reply to it, not only the student's side.
    assert "Debrief: Noted" in listening.context


async def test_the_debrief_is_sent_what_was_worked_out_in_the_ask_chat(client, monkeypatch):
    mistake_id = await _logged(client)
    recording = Recording()
    monkeypatch.setattr("app.services.get_analyzer", lambda: recording)

    response = await client.post(
        f"/mistakes/{mistake_id}/debrief",
        json={
            "message": "Use what we just worked out.",
            "context": [
                {"role": "student", "text": "Did I misread what x was?"},
                {"role": "assistant", "text": "Yes - you solved for 3x."},
            ],
        },
    )
    body = response.json()
    # The recording analyzer re-files as a misread only if the ask chat reached it.
    assert body["mistake"]["error_type"] == "misread_question"
    assert [t.text for t in recording.seen[-1].conversation] == [
        "Did I misread what x was?",
        "Yes - you solved for 3x.",
        "Use what we just worked out.",
    ]
    # Kept, so the next look at this question shows where the change came from.
    assert [t["text"] for t in body["turns"]][:3] == [
        "Did I misread what x was?",
        "Yes - you solved for 3x.",
        "Use what we just worked out.",
    ]


async def test_the_ask_chat_still_reads_its_whole_thread_after_a_command(client, monkeypatch):
    """Turns already saved into the debrief are not saved twice - but the tutor
    must still see them, or it forgets the start of its own conversation."""
    mistake_id = await _logged(client)
    listening = Listening()
    monkeypatch.setattr("app.routers.mistakes.get_analyzer", lambda: listening)

    history = [
        {"role": "student", "text": "Consider this in the debrief"},
        {"role": "assistant", "text": "Done."},
    ]
    await client.post(
        f"/mistakes/{mistake_id}/ask",
        json={"question": "And what about choice C?", "history": history, "already_kept": 2},
    )
    assert [t.text for t in listening.conversation] == [
        "Consider this in the debrief",
        "Done.",
        "And what about choice C?",
    ]


async def test_a_second_command_keeps_only_what_is_new(client):
    mistake_id = await _logged(client)
    first = [{"role": "student", "text": "Why 7?"}, {"role": "assistant", "text": "The constant."}]
    await client.post(
        f"/mistakes/{mistake_id}/ask",
        json={"question": "Add that to my debrief", "history": first},
    )
    kept_after_first = len((await client.get(f"/mistakes/{mistake_id}/debrief")).json())

    thread = [
        *first,
        {"role": "student", "text": "Add that to my debrief"},
        {"role": "assistant", "text": "Noted."},
        {"role": "student", "text": "Also I was rushing."},
        {"role": "assistant", "text": "Understood."},
    ]
    await client.post(
        f"/mistakes/{mistake_id}/ask",
        json={"question": "Put that in the debrief too", "history": thread, "already_kept": 4},
    )
    texts = [t["text"] for t in (await client.get(f"/mistakes/{mistake_id}/debrief")).json()]
    assert texts[kept_after_first:kept_after_first + 3] == [
        "Also I was rushing.",
        "Understood.",
        "Put that in the debrief too",
    ]
    assert texts.count("Why 7?") == 1
