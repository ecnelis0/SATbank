"""The analyzer boundary: what the app stores, and what it does when the AI fails."""

from __future__ import annotations

import pytest

from app.analysis import MistakeAnalysis, MistakeInput, StubAnalyzer
from app.models import ErrorType
from tests.conftest import MATH_MISTAKE


async def test_the_stub_returns_a_fully_populated_analysis():
    result = await StubAnalyzer().analyze(MistakeInput(**MATH_MISTAKE))

    assert isinstance(result, MistakeAnalysis)
    assert result.error_type in set(ErrorType)
    assert result.topic and result.why_wrong and result.takeaway and result.trap


async def test_analysis_slots_are_a_closed_vocabulary():
    """Free-text 'why' labels would make the slot view ungroupable."""
    with pytest.raises(ValueError):
        MistakeAnalysis(
            error_type="i just blanked",
            topic="algebra",
            difficulty="medium",
            why_wrong="x",
            correct_reasoning="x",
            takeaway="x",
            trap="x",
        )


async def test_a_failing_analyzer_still_leaves_a_logged_mistake_on_the_ladder(client, monkeypatch):
    from app import services

    class Broken:
        name = "broken"

        async def analyze(self, mistake):
            raise RuntimeError("provider is down")

    monkeypatch.setattr(services, "get_analyzer", lambda: Broken())

    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    stored = (await client.get(f"/mistakes/{mistake_id}")).json()

    assert stored["analysis_status"] == "failed"
    assert "provider is down" in stored["analysis_error"]
    assert stored["why_wrong"] is None
    # The point: the review schedule does not depend on the AI succeeding.
    assert len(stored["reviews"]) == 5


async def test_reanalyze_recovers_a_failed_analysis(client, monkeypatch):
    from app import services

    class Broken:
        name = "broken"

        async def analyze(self, mistake):
            raise RuntimeError("provider is down")

    monkeypatch.setattr(services, "get_analyzer", lambda: Broken())
    mistake_id = (await client.post("/mistakes", json=MATH_MISTAKE)).json()["id"]
    assert (await client.get(f"/mistakes/{mistake_id}")).json()["analysis_status"] == "failed"

    monkeypatch.setattr(services, "get_analyzer", lambda: StubAnalyzer())
    recovered = (await client.post(f"/mistakes/{mistake_id}/reanalyze")).json()

    assert recovered["analysis_status"] == "ready"
    assert recovered["analysis_error"] is None
    assert recovered["why_wrong"]


async def test_health_reports_the_ladder_and_the_active_analyzer(client):
    body = (await client.get("/health")).json()

    assert body["analyzer"] == "stub"
    assert body["ladder"] == ["1h", "24h", "72h", "1w", "1mo"]
