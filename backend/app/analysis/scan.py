"""Read a picture of one question and fill the log form from it.

A Question Bank screenshot, a photo of a worksheet, a page of a practice test:
this returns the fields the student would otherwise retype. Nothing is written.
The student sees the form filled in, fixes whatever the model misread, and logs
it themselves.

What the picture never contains is the answer they actually put. That box stays
empty on purpose; it is the one thing only the student knows, and it is what the
whole debrief is built on.
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ..config import get_settings
from ..models import Section
from .guard import Guarded

ScanKind = Literal["image", "pdf"]


class ScanInput(BaseModel):
    """What a scanner is handed. The bytes are already sniffed and size-checked."""

    kind: ScanKind
    media_type: str
    data: bytes


class ScannedQuestion(BaseModel):
    """What a scanner must return. Doubles as the model's output schema.

    Everything but the question is optional, because a picture showing only the
    question is still worth reading: a half-filled form beats a blank one, and
    the student finishes it.
    """

    model_config = ConfigDict(extra="forbid")

    question_text: str = Field(
        description="The question exactly as it appears, self-contained. Include the "
        "passage, table or setup it depends on, so it can be answered later without "
        "the picture. Transcribe maths as it reads: 'y = sin(3x^2)'. Do not summarise "
        "and do not add anything that is not in the picture."
    )
    choices: list[str] | None = Field(
        default=None,
        description="The answer options in order, as text only. Strip the label the "
        "page prints in front of each one - 'A.', '(B)', '3)' - because the app draws "
        "its own labels, and a kept one renders as 'A. A. The LINE transposon...'. "
        "Null when the question is not multiple choice.",
    )
    correct_answer: str | None = Field(
        default=None,
        description="The correct answer. Give the label alone when the choices are "
        "labelled, e.g. 'C'; otherwise the value, e.g. '12'. Null only if you cannot "
        "tell and cannot work it out.",
    )
    answer_source: Literal["stated", "worked", "unknown"] = Field(
        default="unknown",
        description="'stated' when the picture prints the answer - an answer key, a "
        "'Correct Answer: C' line, a rationale. 'worked' when the picture does not say "
        "and you solved it yourself. 'unknown' when you could not determine it. Never "
        "call a worked answer 'stated': the student needs to know which to trust.",
    )
    section: Section | None = Field(
        default=None,
        description="Which half of the SAT this is: 'reading_writing' for passages, "
        "grammar and rhetoric; 'math' for anything quantitative. Null if unclear.",
    )
    source: str | None = Field(
        default=None,
        description="Where this came from, if the picture says: 'SAT Question Bank, ID "
        "22e4d633', 'Practice Test 4, Q17'. Include the question ID when one is shown. "
        "Null otherwise. Under 200 characters.",
    )
    note: str | None = Field(
        default=None,
        description="Only when there is something about the *picture* the student "
        "should check - 'the passage is cut off on the right', 'the diagram did not "
        "scan'. Null when the read was clean. Not a comment on the question.",
    )


SCAN_PROMPT = """You read a picture of a single SAT practice question and return \
its fields so a student does not have to retype them.

Transcribe, do not interpret. The question text must match the picture word for \
word, including any passage it refers to. Keep the answer choices in their \
original order.

The answer needs care, because the student will revise from whatever you put for \
a month:

* If the page prints the answer - an answer key, a "Correct Answer: C" line, a \
  rationale - use it and set `answer_source` to "stated".
* If the page does not, solve the question yourself, give your answer, and set \
  `answer_source` to "worked". Take the same care you would if you were sitting \
  the test: these questions are written so that a plausible-looking choice is \
  wrong.
* Only use "unknown" when you genuinely cannot determine it.

Never label a worked answer as stated. The student is told which it was, and \
that is what lets them trust it or check it.

If the picture holds more than one question, take the one that is the subject of \
the page and say so in `note`. If it is not a question at all, say so in `note` \
and put whatever text you can read in `question_text`."""


class Scanner(Protocol):
    name: str

    async def read(self, scan: ScanInput) -> ScannedQuestion: ...


# --- offline ------------------------------------------------------------------


class StubScanner:
    """Cannot read pictures. Returns an empty form and says why.

    Keeps the endpoint honest with no provider configured: the student gets a
    clear message rather than a silent no-op or invented fields.
    """

    name = "stub"

    async def read(self, scan: ScanInput) -> ScannedQuestion:
        return ScannedQuestion(
            question_text="",
            answer_source="unknown",
            note="The offline reader cannot see pictures. Set AI_PROVIDER=agent or "
            "claude to have this one read, or type the question in yourself.",
        )


def get_scanner() -> Scanner:
    """Mirrors `get_analyzer`: the provider decides, and stub always works."""
    settings = get_settings()
    provider = settings.ai_provider.lower()

    if provider == "claude":
        from .claude import ClaudeScanner

        return Guarded(
            ClaudeScanner(settings.anthropic_api_key, settings.anthropic_model),
            settings.ai_timeout_seconds,
        )

    if provider == "openai":
        from .openai_provider import OpenAIScanner

        return Guarded(
            OpenAIScanner(settings.openai_api_key, settings.openai_model),
            settings.ai_timeout_seconds,
        )

    if provider == "agent":
        from .agent import AgentScanner

        return Guarded(AgentScanner(settings.anthropic_model), settings.ai_timeout_seconds)

    return StubScanner()
