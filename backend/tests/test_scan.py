"""Reading a picture of a question into the log form.

The endpoint answers with what the model read and writes nothing, so the tests
here sit either side of that: what the bytes are decided to be on the way in,
and that a read never becomes a row on the way out.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.analysis.base import AnalysisFailed
from app.analysis.scan import ScanInput, ScannedQuestion, StubScanner, get_scanner
from app.models import Section

SCANNED = {
    "question_text": "Which finding would most directly support the hypothesis?",
    "choices": ["The LINE transposon is active in an octopus brain structure.", "Something else."],
    "correct_answer": "A",
    "answer_source": "worked",
    "section": "reading_writing",
    "source": "SAT Question Bank, ID 22e4d633",
    "note": None,
}


def png(size=(60, 40), colour="red") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, "PNG")
    return buffer.getvalue()


# --- the endpoint -------------------------------------------------------------


async def test_a_picture_is_read_and_nothing_is_written(client):
    """The whole point: a scan fills a form, it does not log a question."""
    response = await client.post("/mistakes/scan", files={"file": ("q.png", png(), "image/png")})
    assert response.status_code == 200, response.text
    assert (await client.get("/mistakes")).json() == []


async def test_the_offline_reader_says_so_instead_of_inventing_fields(client):
    """A blank question plus a note is what the form keys off to refuse the fill.

    A stub that returned plausible-looking text would be filed as if it were
    real and revised from for a month."""
    body = (
        await client.post("/mistakes/scan", files={"file": ("q.png", png(), "image/png")})
    ).json()
    assert body["question_text"] == ""
    assert body["answer_source"] == "unknown"
    assert "cannot see pictures" in body["note"]


async def test_a_pdf_is_recognised_from_its_bytes(client):
    response = await client.post(
        "/mistakes/scan", files={"file": ("page.pdf", b"%PDF-1.4 fake", "application/pdf")}
    )
    assert response.status_code == 200, response.text


async def test_the_declared_type_is_not_trusted(client):
    """A text file claiming to be a PNG is refused on its bytes, not its header."""
    response = await client.post(
        "/mistakes/scan", files={"file": ("q.png", b"just some text", "image/png")}
    )
    assert response.status_code == 415
    assert "not a picture we can read" in response.json()["detail"]


async def test_an_empty_file_is_refused(client):
    response = await client.post("/mistakes/scan", files={"file": ("q.png", b"", "image/png")})
    assert response.status_code == 422
    assert "empty" in response.json()["detail"]


async def test_an_oversized_picture_is_refused(client, monkeypatch):
    from app.routers import mistakes

    monkeypatch.setattr(mistakes, "MAX_BYTES", 100)
    response = await client.post(
        "/mistakes/scan", files={"file": ("q.png", png(size=(400, 400)), "image/png")}
    )
    assert response.status_code == 422
    assert "limit" in response.json()["detail"]


async def test_a_reader_failure_is_a_502_with_the_reason(client, monkeypatch):
    """A dead CLI or a refusal must name itself, not surface as a 500."""
    from app.routers import mistakes

    class Broken:
        name = "broken"

        async def read(self, scan):
            raise AnalysisFailed("the agent returned no result")

    monkeypatch.setattr(mistakes, "get_scanner", lambda: Broken())
    response = await client.post("/mistakes/scan", files={"file": ("q.png", png(), "image/png")})
    assert response.status_code == 502
    assert "the agent returned no result" in response.json()["detail"]


async def test_what_the_reader_returns_is_what_the_form_gets(client, monkeypatch):
    from app.routers import mistakes

    seen: list[ScanInput] = []

    class Recording:
        name = "recording"

        async def read(self, scan):
            seen.append(scan)
            return ScannedQuestion(**SCANNED)

    monkeypatch.setattr(mistakes, "get_scanner", lambda: Recording())
    body = (
        await client.post("/mistakes/scan", files={"file": ("q.png", png(), "image/png")})
    ).json()

    assert body["correct_answer"] == "A"
    assert body["answer_source"] == "worked"
    assert body["section"] == "reading_writing"
    assert seen[0].kind == "image"
    assert seen[0].media_type == "image/png"


# --- the contract -------------------------------------------------------------


async def test_the_stub_never_guesses_at_a_question():
    scanned = await StubScanner().read(
        ScanInput(kind="image", media_type="image/png", data=png())
    )
    assert scanned.question_text == ""
    assert scanned.correct_answer is None
    assert scanned.answer_source == "unknown"


def test_only_the_question_is_required():
    """A picture with no answer key still fills the question and the choices."""
    scanned = ScannedQuestion(question_text="q", choices=["one", "two"])
    assert scanned.correct_answer is None
    assert scanned.answer_source == "unknown"
    assert set(ScannedQuestion.model_json_schema()["required"]) == {"question_text"}


def test_a_worked_answer_is_distinguishable_from_a_printed_one():
    """The distinction the student is shown, so they know what to check."""
    assert ScannedQuestion(question_text="q", answer_source="stated").answer_source == "stated"
    assert ScannedQuestion(question_text="q", answer_source="worked").answer_source == "worked"
    with pytest.raises(ValueError):
        ScannedQuestion(question_text="q", answer_source="made up")


def test_the_section_is_the_bank_s_own_enum_not_free_text():
    """Anything else would not survive being posted back to /mistakes."""
    assert ScannedQuestion(question_text="q", section="math").section is Section.math
    with pytest.raises(ValueError):
        ScannedQuestion(question_text="q", section="Biology")


def test_the_provider_decides_the_reader(monkeypatch):
    from app import config

    for provider, expected in (("agent", "agent"), ("stub", "stub"), ("nonsense", "stub")):
        monkeypatch.setenv("AI_PROVIDER", provider)
        config.get_settings.cache_clear()
        assert get_scanner().name == expected
    config.get_settings.cache_clear()


# --- the agent adapter --------------------------------------------------------


async def test_the_picture_is_written_to_disk_for_the_agent_to_read(monkeypatch, tmp_path):
    """The CLI's Read tool opens the file; nothing is sent inline."""
    import claude_agent_sdk

    from app.analysis.agent import AgentScanner

    calls: list[dict] = []

    async def fake_query(*, prompt, options=None, transport=None):
        calls.append({"prompt": prompt, "options": options})
        yield claude_agent_sdk.ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="s",
            stop_reason="end_turn",
            total_cost_usd=0.0,
            usage=None,
            result=None,
            structured_output=SCANNED,
            errors=None,
        )

    monkeypatch.setattr(claude_agent_sdk, "query", fake_query)
    scratch = tmp_path / "scratch"
    scratch.mkdir()

    scanned = await AgentScanner("claude-opus-5", mkdtemp=lambda: str(scratch)).read(
        ScanInput(kind="image", media_type="image/png", data=png())
    )

    assert scanned.correct_answer == "A"
    [call] = calls
    options = call["options"]
    assert options.allowed_tools == ["Read"]
    assert options.permission_mode == "bypassPermissions"
    assert options.cwd == str(scratch)
    assert str(scratch / "question.png") in call["prompt"]
    # The temporary file and its directory do not outlive the read.
    assert not scratch.exists()


async def test_the_agent_refuses_a_format_the_cli_cannot_open():
    from app.analysis.agent import AgentScanner

    with pytest.raises(AnalysisFailed, match="image/tiff"):
        await AgentScanner("claude-opus-5").read(
            ScanInput(kind="image", media_type="image/tiff", data=b"II*\x00")
        )
