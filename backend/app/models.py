"""Database model: a mistake, and the fixed review ladder attached to it."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    TypeDecorator,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, selectinload


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid.uuid4().hex


class UtcDateTime(TypeDecorator):
    """A timestamp that is UTC-aware on both sides of the database.

    SQLite has no timezone storage, so a plain ``DateTime(timezone=True)`` column
    silently reads back naive - which blows up the moment it meets a freshly
    constructed aware datetime, and serialises to JSON with no offset for the
    frontend to trust. This normalises on the way in and re-attaches UTC on the
    way out, so SQLite and Postgres behave the same.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Refusing to store a naive datetime; pass an aware one")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


class Section(StrEnum):
    reading_writing = "reading_writing"
    math = "math"


class AnalysisStatus(StrEnum):
    # Logged by hand with the AI deliberately not asked. Not a failure - a choice.
    not_requested = "not_requested"
    pending = "pending"
    ready = "ready"
    failed = "failed"


class ErrorType(StrEnum):
    """The 'why did I get this wrong' slots. The AI must pick exactly one.

    Kept as a closed vocabulary so the bank can be grouped and counted; a free-text
    label per mistake would make the slot view useless.
    """

    careless_arithmetic = "careless_arithmetic"
    misread_question = "misread_question"
    concept_gap = "concept_gap"
    formula_error = "formula_error"
    algebra_slip = "algebra_slip"
    unit_or_conversion = "unit_or_conversion"
    trap_answer = "trap_answer"
    evidence_misread = "evidence_misread"
    vocabulary_gap = "vocabulary_gap"
    grammar_rule_gap = "grammar_rule_gap"
    time_pressure_guess = "time_pressure_guess"
    other = "other"


class Difficulty(StrEnum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class Urgency(StrEnum):
    """How badly this one needs revisiting.

    Ordered most urgent first: a hole in something everything else is built on
    outranks a question that merely matters. `URGENCY_RANK` in `review.py` turns
    this into the order of the review queue.
    """

    fundamental = "fundamental"
    very_important = "very_important"
    important = "important"


class ReviewOutcome(StrEnum):
    correct = "correct"
    wrong = "wrong"
    skipped = "skipped"
    # Not a student action: the rung was retired because a miss restarted the ladder.
    superseded = "superseded"


# A concept is the thing behind a whole family of misses, so the link is many-to-many:
# one question can sit under several concepts, and a concept collects many questions.
concept_mistakes = Table(
    "concept_mistakes",
    Base.metadata,
    Column("concept_id", ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True),
    Column("mistake_id", ForeignKey("mistakes.id", ondelete="CASCADE"), primary_key=True),
)


class Concept(Base):
    """Something worth knowing, written by the student, that questions hang off."""

    __tablename__ = "concepts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(UtcDateTime())

    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    # Optional: plenty of concepts (careless-work habits, pacing) belong to neither.
    section: Mapped[str | None] = mapped_column(String(32), index=True)

    mistakes: Mapped[list[Mistake]] = relationship(
        secondary=concept_mistakes,
        back_populates="concepts",
        order_by="Mistake.created_at.desc()",
    )


class Mistake(Base):
    """One question the student got wrong, plus the AI's analysis of why."""

    __tablename__ = "mistakes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)

    # What the student logged.
    source: Mapped[str | None] = mapped_column(String(200))
    section: Mapped[str] = mapped_column(String(32))
    question_text: Mapped[str] = mapped_column(Text)
    choices: Mapped[list | None] = mapped_column(JSON)
    your_answer: Mapped[str] = mapped_column(Text)
    correct_answer: Mapped[str] = mapped_column(Text)
    student_note: Mapped[str | None] = mapped_column(Text)

    # What the AI produced.
    analysis_status: Mapped[str] = mapped_column(
        String(16), default=AnalysisStatus.pending, index=True
    )
    analysis_error: Mapped[str | None] = mapped_column(Text)
    analyzed_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    analyzed_by: Mapped[str | None] = mapped_column(String(64))
    # Set whenever a human writes over any analysis field. Guards the re-run:
    # re-analysing would silently discard what they wrote.
    analysis_edited_at: Mapped[datetime | None] = mapped_column(UtcDateTime())

    error_type: Mapped[str | None] = mapped_column(String(32), index=True)
    topic: Mapped[str | None] = mapped_column(String(120), index=True)
    difficulty: Mapped[str | None] = mapped_column(String(16))
    urgency: Mapped[str | None] = mapped_column(String(20), index=True)
    why_wrong: Mapped[str | None] = mapped_column(Text)
    correct_reasoning: Mapped[str | None] = mapped_column(Text)
    takeaway: Mapped[str | None] = mapped_column(Text)
    trap: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list | None] = mapped_column(JSON)

    reviews: Mapped[list[ReviewEvent]] = relationship(
        back_populates="mistake",
        cascade="all, delete-orphan",
        order_by="ReviewEvent.due_at",
    )
    images: Mapped[list[MistakeImage]] = relationship(
        back_populates="mistake",
        cascade="all, delete-orphan",
        order_by="MistakeImage.position, MistakeImage.created_at",
    )
    concepts: Mapped[list[Concept]] = relationship(
        secondary=concept_mistakes,
        back_populates="mistakes",
        order_by="Concept.title",
    )


class MistakeImage(Base):
    """A picture of the question, filed against it.

    Only the stored filename lives in the database; the bytes are on disk. The
    filename is generated, never taken from the upload - an attacker-controlled
    name is how you end up writing outside the upload directory.
    """

    __tablename__ = "mistake_images"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    mistake_id: Mapped[str] = mapped_column(
        ForeignKey("mistakes.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)

    filename: Mapped[str] = mapped_column(String(80))
    content_type: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    caption: Mapped[str | None] = mapped_column(String(200))
    # The student's own order, so a question and its answer key stay in sequence.
    position: Mapped[int] = mapped_column(Integer, default=0)

    mistake: Mapped[Mistake] = relationship(back_populates="images")

    @property
    def url(self) -> str:
        """Where the browser fetches it. Serialised straight into `ImageRead`."""
        return f"/uploads/{self.filename}"


class ReviewEvent(Base):
    """One rung of the ladder: this mistake comes back at this time."""

    __tablename__ = "review_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    mistake_id: Mapped[str] = mapped_column(
        ForeignKey("mistakes.id", ondelete="CASCADE"), index=True
    )
    # Which pass over the ladder this belongs to. A missed review restarts the ladder,
    # so cycle 0 is the original run, cycle 1 the one armed by the first miss, etc.
    cycle: Mapped[int] = mapped_column(Integer, default=0)
    step_index: Mapped[int] = mapped_column(Integer)
    interval_label: Mapped[str] = mapped_column(String(8))

    due_at: Mapped[datetime] = mapped_column(UtcDateTime(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    outcome: Mapped[str | None] = mapped_column(String(16))

    mistake: Mapped[Mistake] = relationship(back_populates="reviews")


# The due-queue reads open events ordered by due date; this is its covering index.
Index("ix_review_events_open", ReviewEvent.completed_at, ReviewEvent.due_at)


def blank_collections(mistake: Mistake) -> Mistake:
    """Initialise the collections a brand-new question serialises but never loads.

    A pending question has no concepts and no images. Saying so explicitly stops the
    response from trying to lazy-load them after the commit, which fails as a
    MissingGreenlet rather than as a missing field. Kept next to `mistake_options`
    because the two lists must be added to together.
    """
    mistake.concepts = []
    mistake.images = []
    return mistake


def mistake_options() -> tuple:
    """Everything `MistakeRead` serialises, eager-loaded.

    One place, because a missing relationship here is not a missing field - it is a
    MissingGreenlet at response time, on whichever endpoint was forgotten.
    """
    return (
        selectinload(Mistake.reviews),
        selectinload(Mistake.concepts),
        selectinload(Mistake.images),
    )
