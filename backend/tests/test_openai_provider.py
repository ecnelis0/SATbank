"""The OpenAI provider: the schema it sends, and what it does with what comes back."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from app.analysis.base import (
    AnalysisFailed,
    CoachReport,
    MistakeAnalysis,
    MistakeInput,
    Turn,
    VideoSummary,
)
from app.analysis.openai_provider import UNSUPPORTED, OpenAIAnalyzer, OpenAIScanner, strict_schema
from app.analysis.scan import ScanInput, ScannedQuestion
from app.query import BankQuery, Vocabulary

# --- the schema OpenAI will actually accept -----------------------------------


@pytest.mark.parametrize(
    "model", [MistakeAnalysis, VideoSummary, BankQuery, ScannedQuestion, CoachReport]
)
def test_the_schema_drops_everything_strict_mode_rejects(model):
    """Pydantic emits maxLength, maxItems and default; strict mode rejects the
    whole request over any one of them, naming it."""
    rendered = json.dumps(strict_schema(model))
    for keyword in UNSUPPORTED:
        assert f'"{keyword}"' not in rendered, keyword


def test_every_object_forbids_extras_and_requires_everything():
    """The other half of strict mode: a property left out of `required` is a
    request OpenAI refuses."""

    def check(node):
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                assert node.get("additionalProperties") is False
                assert sorted(node.get("required", [])) == sorted(node.get("properties", {}))
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for item in node:
                check(item)

    check(strict_schema(MistakeAnalysis))


def test_the_schema_keeps_the_fields_themselves():
    """Trimming must not take the content with it."""
    properties = strict_schema(MistakeAnalysis)["properties"]
    for field in ("headline", "why_wrong", "correct_reasoning", "takeaway", "patterns"):
        assert field in properties
    assert properties["headline"]["description"]


# --- a stand-in client --------------------------------------------------------


class FakeCompletions:
    def __init__(self, content=None, refusal=None, raises=None):
        self.content = content
        self.refusal = refusal
        self.raises = raises
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        message = SimpleNamespace(content=self.content, refusal=self.refusal)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def fake_client(**kwargs):
    completions = FakeCompletions(**kwargs)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


ANALYSIS = {
    "error_type": "careless_arithmetic",
    "topic": "linear equations",
    "difficulty": "medium",
    "urgency": "important",
    "headline": "You solved for 3x and stopped.",
    "why_wrong": "You stopped a step early.",
    "correct_reasoning": "1. Subtract 7.\n2. Divide by 3.",
    "takeaway": "Finish the division.",
    "trap": "15 is 3x.",
    "concepts": [],
    "patterns": [],
}

MISTAKE = MistakeInput(
    section="math",
    question_text="If 3x + 7 = 22, what is x?",
    your_answer="15",
    correct_answer="5",
)


async def test_an_analysis_comes_back_parsed():
    client, calls = fake_client(content=json.dumps(ANALYSIS))
    result = await OpenAIAnalyzer(None, "gpt-4o", client=client).analyze(MISTAKE)

    assert isinstance(result, MistakeAnalysis)
    assert result.headline == "You solved for 3x and stopped."
    # And it asked for structured output, strictly.
    sent = calls.calls[0]["response_format"]
    assert sent["type"] == "json_schema"
    assert sent["json_schema"]["strict"] is True


async def test_the_prompt_sent_is_the_shared_one():
    """Both providers must ask for the same thing; two copies drifting apart is
    how one of them quietly starts behaving differently."""
    from app.analysis.claude import SYSTEM_PROMPT

    client, calls = fake_client(content=json.dumps(ANALYSIS))
    await OpenAIAnalyzer(None, "gpt-4o", client=client).analyze(MISTAKE)

    assert calls.calls[0]["messages"][0]["content"] == SYSTEM_PROMPT
    assert MISTAKE.question_text in calls.calls[0]["messages"][1]["content"]


async def test_a_refusal_is_a_failure_not_an_empty_analysis():
    client, _ = fake_client(content=None, refusal="I will not")
    with pytest.raises(AnalysisFailed) as caught:
        await OpenAIAnalyzer(None, "gpt-4o", client=client).analyze(MISTAKE)
    assert "declined" in str(caught.value)


async def test_output_we_cannot_read_is_a_failure():
    client, _ = fake_client(content='{"nonsense": true}')
    with pytest.raises(AnalysisFailed):
        await OpenAIAnalyzer(None, "gpt-4o", client=client).analyze(MISTAKE)


async def test_an_api_error_becomes_an_analysis_failure():
    """So the callers' existing handling covers it — a bad key must mark the
    question failed, not take the request down."""
    import openai

    client, _ = fake_client(raises=openai.APIError("bad key", request=None, body=None))
    with pytest.raises(AnalysisFailed):
        await OpenAIAnalyzer(None, "gpt-4o", client=client).analyze(MISTAKE)


async def test_the_chat_returns_text_not_a_schema():
    client, calls = fake_client(content="Because you stopped a step early.")
    answer = await OpenAIAnalyzer(None, "gpt-4o", client=client).discuss(
        "the question", [Turn(role="student", text="why?")]
    )
    assert answer == "Because you stopped a step early."
    assert "response_format" not in calls.calls[0]


async def test_the_conversation_keeps_who_said_what():
    client, calls = fake_client(content="ok")
    await OpenAIAnalyzer(None, "gpt-4o", client=client).discuss(
        "context",
        [Turn(role="student", text="why?"), Turn(role="assistant", text="because")],
    )
    roles = [m["role"] for m in calls.calls[0]["messages"]]
    assert roles == ["system", "user", "user", "assistant"]


async def test_interpret_says_what_went_wrong_in_its_own_words():
    client, _ = fake_client(content='{"not": "a query"}')
    with pytest.raises(AnalysisFailed) as caught:
        await OpenAIAnalyzer(None, "gpt-4o", client=client).interpret(
            "everything from March", date(2026, 3, 1), Vocabulary()
        )
    assert "as a search" in str(caught.value)


# --- the scanner --------------------------------------------------------------


async def test_a_picture_is_sent_as_an_image():
    client, calls = fake_client(
        content=json.dumps({"question_text": "If 3x + 7 = 22…", "answer_source": "worked"})
    )
    scanned = await OpenAIScanner(None, "gpt-4o", client=client).read(
        ScanInput(kind="image", media_type="image/png", data=b"\x89PNG")
    )
    assert isinstance(scanned, ScannedQuestion)
    content = calls.calls[0]["messages"][1]["content"]
    assert content[0]["type"] == "image_url"
    assert content[0]["image_url"]["url"].startswith("data:image/png;base64,")


async def test_a_pdf_says_so_rather_than_failing_deep_in_the_sdk():
    client, _ = fake_client(content="{}")
    with pytest.raises(AnalysisFailed) as caught:
        await OpenAIScanner(None, "gpt-4o", client=client).read(
            ScanInput(kind="pdf", media_type="application/pdf", data=b"%PDF")
        )
    assert "Screenshot" in str(caught.value)


@pytest.mark.parametrize(
    "model", [MistakeAnalysis, VideoSummary, BankQuery, ScannedQuestion, CoachReport]
)
def test_no_ref_survives_the_conversion(model):
    """OpenAI rejects a $ref that has anything written beside it, and Pydantic
    writes `{"$ref": …, "description": …}` for every enum field. The live API
    said so by name; the first version of these tests did not catch it."""
    rendered = json.dumps(strict_schema(model))
    assert '"$ref"' not in rendered
    assert '"$defs"' not in rendered


def test_inlining_keeps_both_the_enum_and_its_description():
    """Dropping the siblings instead would have been the easy fix, and would have
    thrown away prompt text — the enums are where the guidance matters most."""
    error_type = strict_schema(MistakeAnalysis)["properties"]["error_type"]
    assert len(error_type["enum"]) == 12
    assert error_type["description"]


def test_a_list_over_its_limit_is_trimmed_rather_than_failing_the_whole_answer():
    """Strict mode cannot carry maxItems, so OpenAI is never told the limit. The
    live API cited seven questions where six are allowed, and the whole-bank
    analysis was thrown away for it."""
    from app.analysis.base import CoachPoint

    point = CoachPoint(title="t", detail="d", question_ids=[str(i) for i in range(9)])
    assert point.question_ids == [str(i) for i in range(6)]
    report = CoachReport(overview="o", next_steps=["s"] * 8)
    assert len(report.next_steps) == 5


def test_an_over_long_reply_is_trimmed_rather_than_losing_the_debrief():
    analysis = MistakeAnalysis.model_validate(
        {
            "error_type": "other",
            "topic": "t",
            "difficulty": "easy",
            "urgency": "important",
            "why_wrong": "w",
            "correct_reasoning": "1. c",
            "takeaway": "k",
            "trap": "p",
            "reply": "x" * 3000,
            "headline": "h" * 500,
        }
    )
    assert len(analysis.reply) == 1500
    assert len(analysis.headline) == 200
