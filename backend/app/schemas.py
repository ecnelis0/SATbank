"""Request and response bodies."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import Difficulty, ErrorType, ReviewOutcome, Section


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
    error_type: ErrorType | None
    topic: str | None
    difficulty: Difficulty | None
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
    by_topic: list[SlotCount]
    by_section: list[SlotCount]
