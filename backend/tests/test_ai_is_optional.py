"""The app without AI: what still works, and what fails without taking it down."""

from __future__ import annotations

import asyncio

import pytest

from app.analysis.base import AnalysisFailed
from app.analysis.guard import Guarded
from tests.conftest import MATH_MISTAKE

# --- nothing may hang for ever ------------------------------------------------


async def test_a_provider_that_never_answers_is_abandoned():
    """The one failure the app cannot recover from on its own. Without a ceiling
    the call waits for ever, holding a request or a background task open, and
    enough of those make the app look dead when only the model is."""

    class Hangs:
        name = "hangs"

        async def analyze(self, mistake):
            await asyncio.sleep(60)

    guarded = Guarded(Hangs(), seconds=0.05)
    with pytest.raises(AnalysisFailed) as caught:
        await guarded.analyze(None)
    assert "did not answer" in str(caught.value)


async def test_a_provider_that_answers_in_time_is_untouched():
    class Works:
        name = "works"

        async def analyze(self, mistake):
            return "an analysis"

    assert await Guarded(Works(), seconds=5).analyze(None) == "an analysis"


async def test_the_guard_covers_every_method_not_a_chosen_few():
    """Written as a proxy so that adding a method to the protocol cannot quietly
    add an unguarded path."""

    class Hangs:
        name = "hangs"

        async def discuss(self, *_):
            await asyncio.sleep(60)

        async def read_video(self, *_):
            await asyncio.sleep(60)

    guarded = Guarded(Hangs(), seconds=0.05)
    for call in (guarded.discuss("x", []), guarded.read_video(None)):
        with pytest.raises(AnalysisFailed):
            await call


async def test_the_guard_keeps_the_providers_name():
    class Named:
        name = "claude"

    assert Guarded(Named(), seconds=1).name == "claude"


# --- what works with no model at all ------------------------------------------


async def test_logging_without_a_debrief_touches_no_model(client, monkeypatch):
    """Logging, reviewing and browsing have to work when usage has run out."""

    def explode():
        raise AssertionError("no model should be constructed for this")

    monkeypatch.setattr("app.services.get_analyzer", explode)

    logged = await client.post("/mistakes", json=MATH_MISTAKE, params={"analyze": False})
    assert logged.status_code == 201
    assert logged.json()["analysis_status"] == "not_requested"


async def test_reviewing_touches_no_model(client, monkeypatch):
    logged = (
        await client.post("/mistakes", json=MATH_MISTAKE, params={"analyze": False})
    ).json()

    def explode():
        raise AssertionError("no model should be constructed for this")

    monkeypatch.setattr("app.services.get_analyzer", explode)

    due = await client.get("/reviews/due")
    assert due.status_code == 200
    assert (await client.get("/bank" if False else f"/mistakes/{logged['id']}")).status_code == 200
    assert (await client.get("/stats")).status_code == 200
    assert (await client.get("/concepts")).status_code == 200


async def test_a_failed_debrief_keeps_the_question_and_the_ladder(client, monkeypatch):
    """Running out of usage must cost the debrief and nothing else."""

    class Broken:
        name = "broken"

        async def analyze(self, mistake):
            raise AnalysisFailed("out of usage")

    monkeypatch.setattr("app.services.get_analyzer", lambda: Broken())

    logged = (
        await client.post("/mistakes", json=MATH_MISTAKE, params={"analyze": True})
    ).json()
    fetched = (await client.get(f"/mistakes/{logged['id']}")).json()

    assert fetched["analysis_status"] == "failed"
    assert "out of usage" in fetched["analysis_error"]
    # The question is still logged, and still on the ladder.
    assert fetched["question_text"] == MATH_MISTAKE["question_text"]
    assert len(fetched["reviews"]) == 5


async def test_a_failed_scan_is_a_message_not_a_crash(client, monkeypatch):
    class Broken:
        name = "broken"

        async def read(self, scan):
            raise AnalysisFailed("out of usage")

    monkeypatch.setattr("app.routers.mistakes.get_scanner", lambda: Broken())

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    response = await client.post(
        "/mistakes/scan", files={"file": ("q.png", png, "image/png")}
    )
    # A refusal the student can act on, not a 500 and not a hung request.
    assert response.status_code in (415, 422, 502)
    assert response.json()["detail"]
