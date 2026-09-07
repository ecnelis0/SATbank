"""The analyzer contract.

Everything the student sees under "why I got this wrong" comes from an analyzer.
The app never hand-authors that text; it only stores and organises what comes back.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from ..models import Difficulty, ErrorType, Urgency


class MistakeInput(BaseModel):
    """What an analyzer is given. Deliberately not the ORM object."""

    section: str
    question_text: str
    choices: list[str] | None = None
    your_answer: str
    correct_answer: str
    source: str | None = None
    student_note: str | None = None


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
    tags: list[str] = Field(
        default_factory=list,
        description="Two to four extra lowercase keywords for filtering the bank.",
    )


class AnalysisFailed(RuntimeError):
    """The analyzer could not produce an analysis. The mistake is still saved."""


class Analyzer(Protocol):
    name: str

    async def analyze(self, mistake: MistakeInput) -> MistakeAnalysis: ...
