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
    # The concepts the student already keeps - written by hand, promoted from a
    # pattern, or read out of a video. The debrief checks the question against
    # these so it is filed as it is logged rather than months later by hand.
    known_concepts: list[ConceptBrief] = Field(default_factory=list)


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
    headline: str = Field(
        default="",
        max_length=200,
        description="One sentence, under 20 words, naming what actually went wrong "
        "on this question. The first thing the student reads and sometimes the only "
        "thing: 'You solved for 3x and stopped before dividing.' Not a restatement "
        "of the question, not 'you made an error' - the specific move.",
    )
    why_wrong: str = Field(
        description="Two to four sentences addressed to the student, explaining what "
        "their specific answer suggests they did, not just that it was incorrect."
    )
    correct_reasoning: str = Field(
        description="The correct route to the answer, as numbered steps: '1. …' on "
        "its own line, then '2. …', and so on. One step per line, no blank lines "
        "between them - the app spaces them out. Each step is a thing to do, short "
        "enough to follow while looking at the question."
    )
    takeaway: str = Field(
        description="One sentence the student should remember next time they see this. "
        "A rule, not a summary."
    )
    trap: str = Field(
        description="What made the wrong answer attractive - the specific trap this "
        "question sets. One or two sentences."
    )
    concepts: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="Titles of concepts from the list you were given that this "
        "question is genuinely an instance of, copied exactly. These are the "
        "student's own revision notes, so file the question where they would look "
        "for it. Leave empty when none really apply - a question filed under a "
        "concept it only loosely touches makes that concept useless, and an empty "
        "list is a perfectly good answer. Never invent a title that is not listed.",
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


class ConceptProposal(BaseModel):
    """The case for turning a pattern into a concept the student keeps.

    A suggestion that only says "you did this 11 times" is a statistic. What makes
    it worth acting on is the three things below: the rule behind the misses, the
    case for writing it down, and what went wrong every time.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        max_length=200,
        description="What to call the concept. The rule or idea behind the misses, "
        "not the habit - the pattern is already named. Something the student would "
        "recognise in a revision list.",
    )
    why_a_concept: str = Field(
        max_length=800,
        description="Two or three sentences on why these questions belong together "
        "and why this is worth writing down, pointing at what they actually share.",
    )
    what_went_wrong: str = Field(
        max_length=800,
        description="What the student did, across all of them, in the second person. "
        "The single recurring move - 'every time, you went to the answers before you "
        "had written down what the question was asking for'.",
    )
    body: str = Field(
        max_length=2000,
        description="The concept itself, as the student would want it written in "
        "their own notes: the rule, and how to apply it next time. This is what "
        "goes in the concept's body if they accept.",
    )


class ConceptBrief(BaseModel):
    """A concept as the analyzer sees it when deciding whether it applies."""

    title: str
    body: str | None = None


class ConceptMatch(BaseModel):
    """Which questions belong under one concept."""

    model_config = ConfigDict(extra="forbid")

    concept_title: str = Field(
        description="Copied exactly from the concepts you were given."
    )
    mistake_ids: list[str] = Field(
        default_factory=list,
        description="The ids of the questions this concept genuinely explains.",
    )


class Filing(BaseModel):
    """The whole filing decision, for a batch of questions against a set of concepts."""

    model_config = ConfigDict(extra="forbid")

    matches: list[ConceptMatch] = Field(default_factory=list)


class VideoInput(BaseModel):
    """What a video summariser is given."""

    title: str | None = None
    author: str | None = None
    subject: str | None = None
    # The student's own instruction for this video. Followed over the defaults.
    directions: str | None = None
    transcript: str
    truncated: bool = False
    has_timestamps: bool = True
    # Concepts already in this bank, so a second video on the same rule adds to it
    # rather than creating a near-duplicate beside it.
    known_concepts: list[str] = Field(default_factory=list)


class VideoConcept(BaseModel):
    """One teachable idea out of a video."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        max_length=200,
        description="The rule or idea, named the way a student would look it up - "
        "'Semicolons join two independent clauses'. Not 'Part 3' and not the "
        "video's own section heading. If a concept you were given is the same "
        "idea, reuse its exact wording.",
    )
    body: str = Field(
        max_length=2000,
        description="The concept as a revision note: what the rule is, and how to "
        "apply it. Include the video's own examples where they earn their place. "
        "Written to be read without the video open.",
    )
    start_seconds: int | None = Field(
        default=None,
        description="Seconds from the start of the video where this is explained, "
        "taken from the [123s] marks in the transcript. Null if you cannot tell.",
    )


class VideoSummary(BaseModel):
    """What a video summariser must return."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(
        max_length=2000,
        description="What the video covers and who it is for, in a few sentences.",
    )
    concepts: list[VideoConcept] = Field(
        default_factory=list,
        max_length=25,
        description="The teachable ideas, in the order the video takes them.",
    )


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

    async def file_questions(self, concepts: list[ConceptBrief], digest: str) -> Filing:
        """Decide which already-logged questions belong under which concepts."""
        ...

    async def read_video(self, video: VideoInput) -> VideoSummary:
        """Turn a video's transcript into concepts the student can revise from."""
        ...

    async def propose_concept(self, pattern: str, summary: str, digest: str) -> ConceptProposal:
        """Make the case for promoting a pattern into a concept, from its questions."""
        ...

    async def discuss(self, context: str, conversation: list[Turn]) -> str:
        """Answer a follow-up about one question, given that question and its debrief.

        Separate from `summarise` because the two are asked different things: this
        one is a tutor talking about a single question the student has in front of
        them, and it may explain, re-word and work through - `summarise` may only
        report the rows it was handed.
        """
        ...
