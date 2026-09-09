"""The claim this file exists to defend: paste an API key and everything works.

The real Anthropic SDK, driven against a stand-in endpoint over a real HTTP stack.
Between this and production only the host and the credential differ - so if the
request shape, the structured-output plumbing or the response parsing were wrong,
these fail here rather than the first time the student pays for a call.
"""

from __future__ import annotations

from datetime import date

import httpx2
import pytest

from app.analysis.base import MistakeInput
from app.analysis.claude import ClaudeAnalyzer
from app.models import Difficulty, ErrorType, Urgency
from app.query import BankQuery, Vocabulary
from tests.fakes import anthropic_stub

TODAY = date(2026, 9, 7)


@pytest.fixture
def analyzer():
    anthropic_stub.reset()
    # httpx2, not httpx: the SDK ships its own fork and rejects the other one.
    client = httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=anthropic_stub.app),
        base_url="http://anthropic.test",
    )
    yield ClaudeAnalyzer(
        "sk-ant-test", "claude-opus-5", http_client=client, base_url="http://anthropic.test"
    )


async def test_the_debrief_comes_back_validated(analyzer):
    result = await analyzer.analyze(
        MistakeInput(
            section="math",
            question_text="A circle has a circumference of 12π. What is its area?",
            your_answer="12π",
            correct_answer="36π",
        )
    )

    # Not "a dict came back": the closed vocabularies really were satisfied.
    assert result.error_type in set(ErrorType)
    assert result.urgency in set(Urgency)
    assert result.difficulty in set(Difficulty)
    assert result.why_wrong and result.takeaway is not None


async def test_the_request_is_the_shape_the_api_expects(analyzer):
    await analyzer.analyze(
        MistakeInput(
            section="math",
            question_text="q",
            your_answer="1",
            correct_answer="2",
        )
    )

    sent = anthropic_stub.seen[-1]
    assert sent["model"] == "claude-opus-5"
    # Adaptive thinking, not a budget_tokens config that current models reject.
    assert sent["thinking"] == {"type": "adaptive"}
    assert "budget_tokens" not in sent.get("thinking", {})
    # Structured output rather than prose to scrape.
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert sent["max_tokens"] >= 4096


async def test_a_question_about_the_bank_comes_back_as_a_filter(analyzer):
    query = await analyzer.interpret(
        "very important circles questions from the past 3 months",
        TODAY,
        Vocabulary(topics=["circles"], concepts=["Circumference gives the radius"]),
    )

    assert isinstance(query, BankQuery)
    assert query.limit >= 1


async def test_the_model_is_told_what_this_bank_contains(analyzer):
    """Without the vocabulary it would filter on strings that match nothing."""
    await analyzer.interpret(
        "the circles ones",
        TODAY,
        Vocabulary(
            topics=["circles", "linear equations"],
            concepts=["Circumference gives the radius"],
            sources=["Bluebook Practice Test 4"],
        ),
    )

    prompt = anthropic_stub.seen[-1]["messages"][0]["content"]
    assert "circles" in prompt
    assert "linear equations" in prompt
    assert "Circumference gives the radius" in prompt
    assert TODAY.isoformat() in prompt


async def test_the_summary_is_plain_text(analyzer):
    answer = await analyzer.summarise("what am I worst at", "4 question(s) matched.")

    assert isinstance(answer, str) and answer.strip()
    # No structured output on this one - it is prose by design.
    assert "output_config" not in anthropic_stub.seen[-1]


async def test_a_refusal_is_reported_rather_than_returned_as_an_analysis(analyzer, monkeypatch):
    from app.analysis.base import AnalysisFailed

    monkeypatch.setattr(anthropic_stub, "STOP_REASON", "refusal")
    with pytest.raises(AnalysisFailed):
        await analyzer.analyze(
            MistakeInput(section="math", question_text="q", your_answer="1", correct_answer="2")
        )


async def test_the_model_is_told_that_repetition_answers_a_consistency_question(analyzer):
    """The student's ask: "which questions have I consistently been getting wrong"."""
    await analyzer.summarise(
        "which questions have I consistently been getting wrong in the past month",
        "3 question(s) matched.\n"
        "2 question(s) have been missed again on review, 5 time(s) in total.\n"
        "Topics that keep coming back: inverse trig (4 repeat misses)",
    )

    sent = anthropic_stub.seen[-1]
    system = sent["system"]
    # Told that both kinds of pattern count: several different questions in one
    # area, and the same question coming back wrong.
    assert "questions missed in the same topic" in system
    assert "came round again" in system
    assert "A single question wrong once is not a pattern" in system
    # And given the counts themselves.
    assert "inverse trig (4 repeat misses)" in sent["messages"][0]["content"]


async def test_a_consistency_question_is_read_as_a_date_range(analyzer):
    await analyzer.interpret(
        "what have I consistently got wrong in the past month",
        TODAY,
        Vocabulary(topics=["inverse trig"]),
    )

    system = anthropic_stub.seen[-1]["system"]
    assert "consistently been getting wrong" in system
    assert "logged_after" in system
