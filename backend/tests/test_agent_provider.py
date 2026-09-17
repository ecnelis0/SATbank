"""The Claude Agent SDK provider, without spawning the CLI.

`claude_agent_sdk.query` is replaced with a fake that records the options it was
given and yields a canned ResultMessage, so what is tested is our side of the
seam: which prompts and schemas go in, and how the result is validated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pytest

from app.analysis.agent import AgentAnalyzer
from app.analysis.base import AnalysisFailed, MistakeInput
from app.query import Vocabulary
from app.readiness import analyzer_ready

TODAY = date(2026, 9, 16)


@dataclass
class FakeResult:
    structured_output: Any = None
    result: str | None = None
    is_error: bool = False
    subtype: str = "success"
    stop_reason: str | None = "end_turn"
    errors: list[str] | None = None


@pytest.fixture
def agent(monkeypatch):
    """Patches the SDK so `query` yields what the test scripts, and records calls."""
    import claude_agent_sdk

    calls: list[dict] = []
    replies: list[FakeResult] = []

    async def fake_query(*, prompt, options=None, transport=None):
        calls.append({"prompt": prompt, "options": options})
        reply = replies.pop(0) if replies else FakeResult()
        yield claude_agent_sdk.ResultMessage(
            subtype=reply.subtype,
            duration_ms=1,
            duration_api_ms=1,
            is_error=reply.is_error,
            num_turns=1,
            session_id="s",
            stop_reason=reply.stop_reason,
            total_cost_usd=0.0,
            usage=None,
            result=reply.result,
            structured_output=reply.structured_output,
            errors=reply.errors,
        )

    monkeypatch.setattr(claude_agent_sdk, "query", fake_query)
    return calls, replies


ANALYSIS = {
    "error_type": "concept_gap",
    "topic": "inference",
    "difficulty": "hard",
    "urgency": "fundamental",
    "why_wrong": "You picked the choice the passage never supports.",
    "correct_reasoning": "The last sentence is where the claim lands.",
    "takeaway": "Answer what the text forces, not what it allows.",
    "trap": "B restates a detail rather than the argument.",
}


async def test_analyze_asks_for_the_structured_schema_and_no_tools(agent):
    calls, replies = agent
    replies.append(FakeResult(structured_output=ANALYSIS))

    result = await AgentAnalyzer("claude-opus-5").analyze(
        MistakeInput(
            section="reading_writing",
            question_text="What does the text suggest?",
            your_answer="B",
            correct_answer="D",
        )
    )

    assert result.topic == "inference"
    [call] = calls
    options = call["options"]
    assert options.model == "claude-opus-5"
    # No tools: this provider only reasons about text it was handed, and a
    # permission prompt would hang a headless subprocess.
    assert options.allowed_tools == []
    assert options.output_format["type"] == "json_schema"
    assert "error_type" in options.output_format["schema"]["properties"]
    # The student's own answer has to reach the model, or the debrief is generic.
    assert "B" in call["prompt"]
    assert "D" in call["prompt"]


async def test_interpret_hands_over_the_date_and_the_bank_s_own_words(agent):
    calls, replies = agent
    replies.append(FakeResult(structured_output={"section": ["reading_writing"]}))

    query = await AgentAnalyzer("claude-opus-5").interpret(
        "reading questions", TODAY, Vocabulary()
    )

    assert query.section == ["reading_writing"]
    assert "Today is 2026-09-16" in calls[0]["prompt"]


async def test_summarise_returns_prose_with_no_schema(agent):
    calls, replies = agent
    replies.append(FakeResult(result="One miss, no pattern yet."))

    text = await AgentAnalyzer("claude-opus-5").summarise("what am I worst at", "digest")

    assert text == "One miss, no pattern yet."
    assert calls[0]["options"].output_format is None
    assert "digest" in calls[0]["prompt"]


async def test_an_error_result_is_reported_not_swallowed(agent):
    _, replies = agent
    replies.append(FakeResult(is_error=True, errors=["not logged in"]))

    with pytest.raises(AnalysisFailed, match="not logged in"):
        await AgentAnalyzer("claude-opus-5").summarise("q", "d")


async def test_a_refusal_is_reported(agent):
    _, replies = agent
    replies.append(FakeResult(stop_reason="refusal"))

    with pytest.raises(AnalysisFailed, match="declined"):
        await AgentAnalyzer("claude-opus-5").summarise("q", "d")


async def test_output_that_does_not_match_the_schema_is_rejected(agent):
    _, replies = agent
    replies.append(FakeResult(structured_output={"topic": "inference"}))  # missing fields

    with pytest.raises(AnalysisFailed, match="did not validate"):
        await AgentAnalyzer("claude-opus-5").analyze(
            MistakeInput(
                section="reading_writing",
                question_text="q",
                your_answer="B",
                correct_answer="D",
            )
        )


# --- readiness ----------------------------------------------------------------


class Settings:
    """Just the two fields the rule reads."""

    def __init__(self, provider: str, key: str | None = None):
        self.ai_provider = provider
        self.anthropic_api_key = key


def test_the_agent_is_ready_without_a_key():
    """The bug this pins: `/ask` asked "is the key set" and so reported the
    agent provider broken while it was answering questions perfectly."""
    assert analyzer_ready(Settings("agent")) is True
    assert analyzer_ready(Settings("agent", None)) is True


def test_the_api_adapter_still_needs_its_key():
    assert analyzer_ready(Settings("claude", "sk-ant-x")) is True
    assert analyzer_ready(Settings("claude", None)) is False


def test_the_stub_is_always_ready_and_nonsense_never_is():
    assert analyzer_ready(Settings("stub")) is True
    assert analyzer_ready(Settings("nonsense")) is False


def test_the_factory_builds_the_agent(monkeypatch):
    from app import config
    from app.analysis import get_analyzer

    monkeypatch.setenv("AI_PROVIDER", "agent")
    config.get_settings.cache_clear()
    get_analyzer.cache_clear()
    assert get_analyzer().name == "agent"
    config.get_settings.cache_clear()
    get_analyzer.cache_clear()
