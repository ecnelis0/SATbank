"""Request and response bodies."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import Difficulty, ErrorType, ReviewOutcome, Section, Urgency


class MistakeCreate(BaseModel):
    section: Section
    question_text: str = Field(min_length=1)
    your_answer: str = Field(min_length=1)
    correct_answer: str = Field(min_length=1)
    choices: list[str] | None = None
    source: str | None = Field(default=None, max_length=200)
    student_note: str | None = None

    @field_validator("question_text", "your_answer", "correct_answer")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


ANALYSIS_FIELDS = (
    "error_type",
    "topic",
    "difficulty",
    "urgency",
    "why_wrong",
    "correct_reasoning",
    "takeaway",
    "trap",
    "tags",
)


class MistakeUpdate(BaseModel):
    """Every field on a mistake is editable, including everything the AI wrote.

    All optional: only the keys actually sent are changed, so a form can save one
    field without having to round-trip the rest.
    """

    section: Section | None = None
    source: str | None = Field(default=None, max_length=200)
    question_text: str | None = None
    choices: list[str] | None = None
    your_answer: str | None = None
    correct_answer: str | None = None
    student_note: str | None = None

    error_type: ErrorType | None = None
    topic: str | None = Field(default=None, max_length=120)
    difficulty: Difficulty | None = None
    urgency: Urgency | None = None
    why_wrong: str | None = None
    correct_reasoning: str | None = None
    takeaway: str | None = None
    trap: str | None = None
    tags: list[str] | None = None

    @field_validator("question_text", "your_answer", "correct_answer")
    @classmethod
    def _not_blanked(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    def touches_analysis(self) -> bool:
        return any(field in self.model_fields_set for field in ANALYSIS_FIELDS)


class ReviewEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    cycle: int
    step_index: int
    interval_label: str
    due_at: datetime
    completed_at: datetime | None
    outcome: ReviewOutcome | None


class MistakeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    section: Section
    source: str | None
    question_text: str
    choices: list[str] | None
    your_answer: str
    correct_answer: str
    student_note: str | None

    analysis_status: str
    analysis_error: str | None
    analyzed_at: datetime | None
    analyzed_by: str | None
    analysis_edited_at: datetime | None
    error_type: ErrorType | None
    topic: str | None
    difficulty: Difficulty | None
    urgency: Urgency | None
    why_wrong: str | None
    correct_reasoning: str | None
    takeaway: str | None
    trap: str | None
    tags: list[str] | None

    reviews: list[ReviewEventRead] = []


class DueReview(BaseModel):
    """A rung that is ready to be reviewed, with the question it belongs to."""

    review: ReviewEventRead
    mistake: MistakeRead


class ReviewComplete(BaseModel):
    outcome: ReviewOutcome

    @field_validator("outcome")
    @classmethod
    def _student_outcomes_only(cls, value: ReviewOutcome) -> ReviewOutcome:
        if value is ReviewOutcome.superseded:
            raise ValueError("'superseded' is set by the ladder, not by the student")
        return value


class ReviewCompleteResult(BaseModel):
    review: ReviewEventRead
    ladder_restarted: bool
    next_due_at: datetime | None


class SlotCount(BaseModel):
    key: str
    count: int


class Stats(BaseModel):
    total_mistakes: int
    due_now: int
    reviews_completed: int
    by_error_type: list[SlotCount]
    by_urgency: list[SlotCount]
    by_topic: list[SlotCount]
    by_section: list[SlotCount]
