"""Asking the bank where the points go: grouped by the database, debriefed by the model."""

from __future__ import annotations

import pytest

from app.analysis import StubAnalyzer
from app.analysis.base import AnalysisFailed, Breakdown, GroupReading
from app.commands import is_breakdown_question
from tests.conftest import MATH_MISTAKE, VERBAL_MISTAKE
from tests.test_ask import _log


@pytest.mark.parametrize(
    "text",
    [
        "What patterns do I have?",
        "Where am I losing the most points?",
        "What do I keep getting wrong in math?",
        "Why do I keep missing evidence questions?",
        "What are my weaknesses?",
        "What are my most common mistakes this month?",
        "where did I go wrong on reading",
        "What am I worst at",
    ],
)
def test_breakdown_questions_are_recognised(text):
    assert is_breakdown_question(text)


@pytest.mark.parametrize(
    "text",
    ["What is due for review now?", "Everything very important from Reading", "circles"],
)
def test_searches_stay_searches(text):
    assert not is_breakdown_question(text)


class Reading(StubAnalyzer):
    name = "reading"

    def __init__(self) -> None:
        self.digest = ""

    async def explain_breakdown(self, digest: str) -> Breakdown:
        self.digest = digest
        return Breakdown(
            summary="Concept gaps cost you the most: 3 questions.",
            groups=[
                GroupReading(
                    key="reason:concept_gap",
                    why="You reach for a formula before checking what is asked.",
                    what_to_do="Write down the quantity asked for first.",
                ),
                GroupReading(key="reason:made_up", why="invented", what_to_do="-"),
            ],
        )


async def _bank(client) -> dict[str, list[str]]:
    gaps = [
        await _log(client, MATH_MISTAKE, error_type="concept_gap") for _ in range(3)
    ]
    trap = [await _log(client, VERBAL_MISTAKE, error_type="trap_answer")]
    return {"concept_gap": gaps, "trap_answer": trap}


async def test_the_answer_groups_the_questions_by_why_they_were_lost(client, monkeypatch):
    ids = await _bank(client)
    reading = Reading()
    monkeypatch.setattr("app.routers.ask.get_analyzer", lambda: reading)

    body = (
        await client.post("/ask", json={"question": "Where am I losing the most points?"})
    ).json()

    assert body["answer"] == "Concept gaps cost you the most: 3 questions."
    reasons = {g["key"]: g for g in body["groups"] if g["kind"] == "reason"}
    gap = reasons["reason:concept_gap"]
    # Counted and listed by the database: exactly the questions filed there.
    assert gap["count"] == 3
    assert sorted(m["id"] for m in gap["mistakes"]) == sorted(ids["concept_gap"])
    assert gap["why"] == "You reach for a formula before checking what is asked."
    assert gap["what_to_do"] == "Write down the quantity asked for first."
    # A group the model said nothing about still lists its questions.
    trap = reasons["reason:trap_answer"]
    assert [m["id"] for m in trap["mistakes"]] == ids["trap_answer"]
    assert trap["why"] is None
    # A group the model invented is not shown.
    assert "reason:made_up" not in {g["key"] for g in body["groups"]}
    # Biggest point-loser first.
    assert body["groups"][0]["key"] == "reason:concept_gap"


async def test_the_model_is_given_what_the_student_said_happened(client, monkeypatch):
    mistake_id = await _log(client, MATH_MISTAKE, error_type="concept_gap")
    await client.post(f"/mistakes/{mistake_id}/debrief", json={"message": "I panicked."})
    reading = Reading()
    monkeypatch.setattr("app.routers.ask.get_analyzer", lambda: reading)

    await client.post("/ask", json={"question": "What do I keep getting wrong?"})

    assert "key=reason:" in reading.digest
    assert MATH_MISTAKE["student_note"] in reading.digest
    assert "they told the debrief: I panicked." in reading.digest


async def test_a_pattern_is_a_group_only_once_it_holds_more_than_one_question(client):
    """The stub names one pattern per topic, so two math questions share one."""
    await _log(client, MATH_MISTAKE)
    await _log(client, MATH_MISTAKE)
    await _log(client, VERBAL_MISTAKE)

    body = (await client.post("/ask", json={"question": "What are my patterns?"})).json()
    patterns = [g for g in body["groups"] if g["kind"] == "pattern"]
    assert len(patterns) == 1
    assert patterns[0]["count"] == 2


async def test_without_a_model_the_groups_still_come_back(client, monkeypatch):
    await _bank(client)

    class Broken(StubAnalyzer):
        async def explain_breakdown(self, digest: str) -> Breakdown:
            raise AnalysisFailed("out of credit")

    monkeypatch.setattr("app.routers.ask.get_analyzer", lambda: Broken())
    body = (await client.post("/ask", json={"question": "Where am I losing points?"})).json()

    assert "out of credit" in body["error"]
    assert {g["key"] for g in body["groups"]} >= {"reason:concept_gap", "reason:trap_answer"}
    assert body["answer"]


async def test_a_plain_search_gets_no_groups(client):
    await _bank(client)
    body = (await client.post("/ask", json={"question": "What is due for review now?"})).json()
    assert body["groups"] == []


async def test_more_than_the_default_page_is_grouped(client):
    """Grouping only the newest 25 would undercount every group."""
    for _ in range(30):
        await _log(client, MATH_MISTAKE, error_type="concept_gap")
    body = (await client.post("/ask", json={"question": "What do I keep getting wrong?"})).json()
    gap = next(g for g in body["groups"] if g["key"] == "reason:concept_gap")
    assert gap["count"] == 30
