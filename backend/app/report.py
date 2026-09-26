"""A period report: what you logged in a window, what you missed, what to work on.

Built as data first and rendered second, so the same report can come back as JSON
for the screen and as a PDF for printing without the two ever disagreeing. Nothing
here asks the model anything - the numbers are counted from rows, and the ranking
that produces "what to work on" is a rule you can read below rather than an
opinion. The assistant's prose sits *next to* this, never in place of it.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, time

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Concept,
    ErrorType,
    Mistake,
    ReviewEvent,
    ReviewOutcome,
    Section,
    Urgency,
    concept_options,
    mistake_options,
    utcnow,
)

# The student-facing names. The backend owns these too, because a PDF is read
# without the app next to it and "concept_gap" is not a sentence.
ERROR_TYPE_LABELS: dict[str, str] = {
    ErrorType.careless_arithmetic: "Careless arithmetic",
    ErrorType.misread_question: "Misread the question",
    ErrorType.concept_gap: "Concept gap",
    ErrorType.formula_error: "Wrong formula",
    ErrorType.algebra_slip: "Algebra slip",
    ErrorType.unit_or_conversion: "Units & conversion",
    ErrorType.trap_answer: "Walked into the trap",
    ErrorType.evidence_misread: "Misread the evidence",
    ErrorType.vocabulary_gap: "Vocabulary gap",
    ErrorType.grammar_rule_gap: "Grammar rule gap",
    ErrorType.time_pressure_guess: "Guessed under time pressure",
    ErrorType.other: "Something else",
}

ERROR_TYPE_BLURBS: dict[str, str] = {
    ErrorType.careless_arithmetic: "You knew the method. The numbers went wrong on the way.",
    ErrorType.misread_question: "You solved a question. Just not the one that was asked.",
    ErrorType.concept_gap: "The idea underneath this question is not yet solid.",
    ErrorType.formula_error: "The right shape of answer, reached with the wrong formula.",
    ErrorType.algebra_slip: "A sign, a term, or a step that got lost in the manipulation.",
    ErrorType.unit_or_conversion: "The quantity was right, the unit was not.",
    ErrorType.trap_answer: "You picked the answer the question was built to make attractive.",
    ErrorType.evidence_misread: "The lines you chose do not say what you took them to say.",
    ErrorType.vocabulary_gap: "A word in the passage or the answers did the damage.",
    ErrorType.grammar_rule_gap: "A rule of punctuation or structure that has not landed yet.",
    ErrorType.time_pressure_guess: "Not a knowledge problem. A clock problem.",
    ErrorType.other: "Does not fit the usual slots.",
}

URGENCY_LABELS: dict[str, str] = {
    Urgency.fundamental: "Fundamental concept",
    Urgency.very_important: "Very important",
    Urgency.important: "Important",
}

SECTION_LABELS: dict[str, str] = {
    Section.reading_writing: "Reading & Writing",
    Section.math: "Math",
}


class Window(BaseModel):
    """The stretch of time the report covers.

    Both ends are optional: "everything I have ever logged" is a legitimate report
    and should not need a made-up start date.
    """

    since: date | None = None
    until: date | None = None

    @property
    def label(self) -> str:
        if self.since and self.until:
            return f"{self.since:%-d %b %Y} to {self.until:%-d %b %Y}"
        if self.since:
            return f"since {self.since:%-d %b %Y}"
        if self.until:
            return f"up to {self.until:%-d %b %Y}"
        return "all time"

    def start_dt(self) -> datetime | None:
        return datetime.combine(self.since, time.min, tzinfo=UTC) if self.since else None

    def end_dt(self) -> datetime | None:
        return datetime.combine(self.until, time.max, tzinfo=UTC) if self.until else None


class Line(BaseModel):
    """One counted row of a breakdown."""

    key: str
    label: str
    count: int
    blurb: str | None = None


class QuestionLine(BaseModel):
    """One question, as it appears in the report's roll-call.

    Carries its own logged date: the whole point of a period report is being able
    to see when each thing happened, not just that it fell inside the window.
    """

    id: str
    logged_at: datetime
    section: str
    section_label: str
    urgency: str | None = None
    urgency_label: str | None = None
    error_type: str | None = None
    error_type_label: str | None = None
    topic: str | None = None
    source: str | None = None
    question_text: str
    your_answer: str
    correct_answer: str
    student_note: str | None = None
    takeaway: str | None = None
    concepts: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ConceptLine(BaseModel):
    id: str
    title: str
    created_at: datetime
    section: str | None = None
    questions_in_window: int = 0
    questions_total: int = 0


class PeriodReport(BaseModel):
    generated_at: datetime
    window: Window
    window_label: str

    logged_count: int
    reviews_answered: int
    reviews_correct: int
    reviews_wrong: int
    reviews_skipped: int
    still_due: int
    untagged_in_window: int

    by_error_type: list[Line] = Field(default_factory=list)
    by_urgency: list[Line] = Field(default_factory=list)
    by_section: list[Line] = Field(default_factory=list)
    by_topic: list[Line] = Field(default_factory=list)
    concepts: list[ConceptLine] = Field(default_factory=list)

    # The report's conclusion, in order. Derived by `_focus` below.
    focus: list[str] = Field(default_factory=list)
    questions: list[QuestionLine] = Field(default_factory=list)


def _lines(counter: Counter[str], labels: dict[str, str], blurbs: dict[str, str] | None = None):
    """Commonest first, then alphabetical, so equal counts do not shuffle between runs."""
    return [
        Line(
            key=key,
            label=labels.get(key, key.replace("_", " ").capitalize()),
            count=count,
            blurb=(blurbs or {}).get(key),
        )
        for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _focus(report_rows: list[Mistake], by_error: Counter[str], by_topic: Counter[str]) -> list[str]:
    """"What to work on", worst first.

    Deliberately a rule rather than a model call: a report that says something
    different every time you generate it for the same month is not a report. The
    order is the order of what costs marks — a repeated diagnosis outranks a
    repeated topic, because the same slip across two topics is one habit to fix.
    """
    focus: list[str] = []

    for key, count in sorted(by_error.items(), key=lambda item: (-item[1], item[0])):
        if count < 2:
            continue
        label = ERROR_TYPE_LABELS.get(key, key)
        focus.append(f"{label} — {count} questions. {ERROR_TYPE_BLURBS.get(key, '')}".strip())

    for topic, count in sorted(by_topic.items(), key=lambda item: (-item[1], item[0])):
        if count < 2:
            continue
        focus.append(f"{topic} — missed {count} times in this window.")

    fundamental = [m for m in report_rows if m.urgency == Urgency.fundamental]
    if fundamental:
        focus.append(
            f"{len(fundamental)} question{'' if len(fundamental) == 1 else 's'} marked a "
            "fundamental concept. These sit underneath everything else — clear them first."
        )

    untagged = [m for m in report_rows if not m.concepts]
    if untagged:
        focus.append(
            f"{len(untagged)} question{'' if len(untagged) == 1 else 's'} filed under no "
            "concept. Until they are tagged they cannot show up as a pattern."
        )

    if not focus:
        focus.append(
            "Nothing repeated in this window. No single habit is costing you marks yet — "
            "keep logging, and the pattern will show."
        )
    return focus


async def build_report(session: AsyncSession, user_id: str, window: Window) -> PeriodReport:
    """Count the window from rows. Every number below is a query, not an estimate."""
    start, end = window.start_dt(), window.end_dt()

    stmt = select(Mistake).where(Mistake.user_id == user_id).options(*mistake_options())
    if start is not None:
        stmt = stmt.where(Mistake.created_at >= start)
    if end is not None:
        stmt = stmt.where(Mistake.created_at <= end)
    rows = list(await session.scalars(stmt.order_by(Mistake.created_at.desc())))

    by_error: Counter[str] = Counter()
    by_urgency: Counter[str] = Counter()
    by_section: Counter[str] = Counter()
    by_topic: Counter[str] = Counter()
    for mistake in rows:
        if mistake.error_type:
            by_error[mistake.error_type] += 1
        if mistake.urgency:
            by_urgency[mistake.urgency] += 1
        by_section[mistake.section] += 1
        if mistake.topic:
            by_topic[mistake.topic] += 1

    # Reviews are counted by when they were *answered*, not when the question was
    # logged: "what did I do this month" includes revising something from March.
    review_stmt = (
        select(ReviewEvent.outcome, func.count())
        .join(Mistake)
        .where(
            Mistake.user_id == user_id,
            ReviewEvent.completed_at.is_not(None),
            ReviewEvent.outcome != ReviewOutcome.superseded,
        )
        .group_by(ReviewEvent.outcome)
    )
    if start is not None:
        review_stmt = review_stmt.where(ReviewEvent.completed_at >= start)
    if end is not None:
        review_stmt = review_stmt.where(ReviewEvent.completed_at <= end)
    outcomes = Counter({outcome: count for outcome, count in await session.execute(review_stmt)})

    # Still due is deliberately *not* windowed. It is the state of the bank right
    # now, and a report that hid a review due today because it was armed last month
    # would be worse than useless.
    still_due = await session.scalar(
        select(func.count())
        .select_from(ReviewEvent)
        .join(Mistake)
        .where(
            Mistake.user_id == user_id,
            ReviewEvent.completed_at.is_(None),
            ReviewEvent.due_at <= utcnow(),
        )
    )

    concept_stmt = (
        select(Concept).where(Concept.user_id == user_id).options(*concept_options())
    )
    in_window = {m.id for m in rows}
    concepts = [
        ConceptLine(
            id=concept.id,
            title=concept.title,
            created_at=concept.created_at,
            section=concept.section,
            questions_in_window=sum(1 for m in concept.mistakes if m.id in in_window),
            questions_total=len(concept.mistakes),
        )
        for concept in await session.scalars(concept_stmt)
    ]
    # Most relevant to this window first; ties broken by the concept's own age so
    # the order is stable.
    concepts.sort(key=lambda c: (-c.questions_in_window, -c.questions_total, c.created_at))

    return PeriodReport(
        generated_at=utcnow(),
        window=window,
        window_label=window.label,
        logged_count=len(rows),
        reviews_answered=sum(outcomes.values()),
        reviews_correct=outcomes.get(ReviewOutcome.correct, 0),
        reviews_wrong=outcomes.get(ReviewOutcome.wrong, 0),
        reviews_skipped=outcomes.get(ReviewOutcome.skipped, 0),
        still_due=still_due or 0,
        untagged_in_window=sum(1 for m in rows if not m.concepts),
        by_error_type=_lines(by_error, ERROR_TYPE_LABELS, ERROR_TYPE_BLURBS),
        by_urgency=_lines(by_urgency, URGENCY_LABELS),
        by_section=_lines(by_section, SECTION_LABELS),
        by_topic=_lines(by_topic, {}),
        concepts=concepts,
        focus=_focus(rows, by_error, by_topic),
        questions=[
            QuestionLine(
                id=m.id,
                logged_at=m.created_at,
                section=m.section,
                section_label=SECTION_LABELS.get(m.section, m.section),
                urgency=m.urgency,
                urgency_label=URGENCY_LABELS.get(m.urgency) if m.urgency else None,
                error_type=m.error_type,
                error_type_label=ERROR_TYPE_LABELS.get(m.error_type) if m.error_type else None,
                topic=m.topic,
                source=m.source,
                question_text=m.question_text,
                your_answer=m.your_answer,
                correct_answer=m.correct_answer,
                student_note=m.student_note,
                takeaway=m.takeaway,
                concepts=[c.title for c in m.concepts],
                tags=list(m.tags or []),
            )
            for m in rows
        ],
    )
