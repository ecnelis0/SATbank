"""The analyzer contract.

Everything the student sees under "why I got this wrong" comes from an analyzer.
The app never hand-authors that text; it only stores and organises what comes back.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ..models import Difficulty, ErrorType, Urgency

if TYPE_CHECKING:
    from ..query import BankQuery


class MistakeInput(BaseModel):
    """What an analyzer is given. Deliberately not the ORM object."""

    section: str
    question_text: str
    choices: list[str] | None = None
    your_answer: str
    correct_answer: str
    source: str | None = None
    student_note: str | None = None
    # The patterns already named in this bank. This is the whole mechanism behind
    # clustering: handed nothing, the model writes a fresh wording for the same
    # habit every time and every pattern ends up with one question under it.
    known_patterns: list[str] = Field(default_factory=list)


class PatternTag(BaseModel):
    """One recurring habit this question is an instance of."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        max_length=120,
        description="Short, reusable name for the habit itself — 'Dropped a negative "
        "sign', 'Answered the question before the one asked', 'Picked the choice that "
        "restates the passage'. Name what the student did or what the trap was, never "
        "the topic: 'quadratics' is a topic and groups nothing useful. If one of the "
        "patterns you were given already means this, reuse its exact wording.",
    )
    why: str = Field(
        max_length=400,
        description="One sentence on how this particular question is an instance of "
        "that pattern, in the second person.",
    )


class MistakeAnalysis(BaseModel):
    """What an analyzer must return. Doubles as the model's output schema."""

    model_config = ConfigDict(extra="forbid")

    error_type: ErrorType = Field(
        description="The single best-fitting reason this student got the question wrong."
    )
    topic: str = Field(
        description="Short SAT topic label, e.g. 'systems of linear equations' or "
        "'command of evidence'. Title-free, lowercase, under 60 characters."
    )
    difficulty: Difficulty
    urgency: Urgency = Field(
        description="How badly this needs revisiting. 'fundamental' when the miss "
        "exposes a hole in something the rest of the section is built on; "
        "'very_important' for a high-frequency skill or a trap they will meet again; "
        "'important' otherwise. Judge the gap, not the question's difficulty."
    )
    why_wrong: str = Field(
        description="Two to four sentences addressed to the student, explaining what "
        "their specific answer suggests they did, not just that it was incorrect."
    )
    correct_reasoning: str = Field(
        description="The correct route to the answer, in steps the student can follow."
    )
    takeaway: str = Field(
        description="One sentence the student should remember next time they see this. "
        "A rule, not a summary."
    )
    trap: str = Field(
        description="What made the wrong answer attractive - the specific trap this "
        "question sets. One or two sentences."
    )
    patterns: list[PatternTag] = Field(
        default_factory=list,
        max_length=3,
        description="The recurring habits this miss is an instance of, most telling "
        "first. One or two is normal; three is the most that is ever useful. Base them "
        "on what went wrong and on the trap, not on the topic — the point is that a "
        "question from algebra and a question from geometry can share one. Reuse a "
        "pattern you were given wherever it fits rather than inventing a near-copy.",
    )


class Turn(BaseModel):
    """One thing said, in a conversation about a single question.

    The history travels with each request rather than living on the server: a
    follow-up is only meaningful next to what was already said, and a chat whose
    thread the API has quietly forgotten is worse than one that never offered it.
    """

    role: Literal["student", "assistant"]
    text: str = Field(min_length=1, max_length=4000)


class AnalysisFailed(RuntimeError):
    """The analyzer could not produce an analysis. The mistake is still saved."""


class Analyzer(Protocol):
    name: str

    async def analyze(self, mistake: MistakeInput) -> MistakeAnalysis: ...

    async def interpret(self, question: str, today: date) -> BankQuery:
        """Turn a question about the bank into a filter the database can run.

        `today` is passed in rather than read from the clock so "the past 3 months"
        resolves to real dates the model can write down.
        """
        ...

    async def summarise(self, question: str, digest: str) -> str:
        """Answer in a sentence or two, using only the rows it is given."""
        ...

    async def discuss(self, context: str, conversation: list[Turn]) -> str:
        """Answer a follow-up about one question, given that question and its debrief.

        Separate from `summarise` because the two are asked different things: this
        one is a tutor talking about a single question the student has in front of
        them, and it may explain, re-word and work through - `summarise` may only
        report the rows it was handed.
        """
        ...
