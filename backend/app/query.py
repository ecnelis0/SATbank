"""Structured queries over the bank.

The assistant does not answer from memory or from a blob of context. It turns a
question into one of these, the database answers it, and only then does the model
get to say anything - so a count is a count and a list is the real list.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Concept,
    ErrorType,
    Mistake,
    ReviewEvent,
    Section,
    Urgency,
    mistake_options,
    utcnow,
)
from .review import URGENCY_RANK

Sort = Literal["newest", "oldest", "most_urgent"]


class Vocabulary(BaseModel):
    """What this particular bank actually contains.

    Handed to the model before it writes a filter. Without it, "questions about
    circles" or "everything under the circumference concept" cannot be turned into a
    filter at all - the model would be guessing at strings it has never seen.
    """

    topics: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)

    def render(self) -> str:
        def block(title: str, values: list[str]) -> str:
            return f"{title}: {', '.join(values) if values else '(none yet)'}"

        return "\n".join(
            [
                block("Topics in this bank", self.topics),
                block("Concepts the student has written", self.concepts),
                block("Sources", self.sources),
            ]
        )


class BankQuery(BaseModel):
    """What the student asked for, in terms the database understands.

    Every list is OR within itself and AND across fields: `urgency=[fundamental,
    very_important], section=[reading_writing]` means "fundamental or very important,
    *and* Reading & Writing".
    """

    model_config = ConfigDict(extra="forbid")

    concept_ids: list[str] = Field(
        default_factory=list,
        description="Concept ids. The category rail sets these; the model uses "
        "`concepts` instead, which takes titles.",
    )
    concepts: list[str] = Field(
        default_factory=list,
        description="Concept titles, copied from the list of concepts you were given. "
        "Matched as substrings, case-insensitively.",
    )
    urgency: list[Urgency] = Field(default_factory=list)
    error_type: list[ErrorType] = Field(default_factory=list)
    section: list[Section] = Field(default_factory=list)
    topics: list[str] = Field(
        default_factory=list,
        description="Topic words to match, e.g. 'circles'. Matched as substrings.",
    )
    text: str | None = Field(
        default=None, description="Words that must appear in the question itself."
    )
    logged_after: date | None = Field(
        default=None,
        description="Only questions logged on or after this date. Resolve relative "
        "phrases like 'the past 3 months' against today's date, given in the prompt.",
    )
    logged_before: date | None = Field(
        default=None, description="Only questions logged on or before this date."
    )
    only_due: bool = Field(default=False, description="Only questions with a review due right now.")
    sort: Sort = "newest"
    limit: int = Field(default=25, ge=1, le=100)


def build_statement(user_id: str, query: BankQuery):
    stmt = select(Mistake).where(Mistake.user_id == user_id).options(*mistake_options())

    if query.concept_ids:
        stmt = stmt.where(Mistake.concepts.any(Concept.id.in_(query.concept_ids)))
    if query.concepts:
        stmt = stmt.where(
            Mistake.concepts.any(
                or_(*[Concept.title.ilike(f"%{title}%") for title in query.concepts])
            )
        )
    if query.urgency:
        stmt = stmt.where(Mistake.urgency.in_([u.value for u in query.urgency]))
    if query.error_type:
        stmt = stmt.where(Mistake.error_type.in_([e.value for e in query.error_type]))
    if query.section:
        stmt = stmt.where(Mistake.section.in_([s.value for s in query.section]))
    if query.topics:
        stmt = stmt.where(or_(*[Mistake.topic.ilike(f"%{topic}%") for topic in query.topics]))
    if query.text:
        stmt = stmt.where(Mistake.question_text.ilike(f"%{query.text}%"))
    if query.logged_after:
        stmt = stmt.where(
            Mistake.created_at >= datetime.combine(query.logged_after, time.min, tzinfo=UTC)
        )
    if query.logged_before:
        stmt = stmt.where(
            Mistake.created_at <= datetime.combine(query.logged_before, time.max, tzinfo=UTC)
        )
    if query.only_due:
        stmt = stmt.where(
            Mistake.reviews.any(
                (ReviewEvent.completed_at.is_(None)) & (ReviewEvent.due_at <= utcnow())
            )
        )

    order = {
        "newest": Mistake.created_at.desc(),
        "oldest": Mistake.created_at.asc(),
    }.get(query.sort)
    stmt = (
        stmt.order_by(order)
        if order is not None
        else stmt.order_by(URGENCY_RANK, Mistake.created_at.desc())
    )

    return stmt.limit(query.limit)


async def run_query(session: AsyncSession, user_id: str, query: BankQuery) -> list[Mistake]:
    result = await session.scalars(build_statement(user_id, query))
    return list(result)


def describe(query: BankQuery) -> str:
    """A plain-English readback of the filter, so the student can see what was searched."""
    parts: list[str] = []
    if query.concepts:
        parts.append("under " + " or ".join(query.concepts))
    if query.concept_ids:
        count = len(query.concept_ids)
        parts.append(f"under {count} concept{'' if count == 1 else 's'}")
    if query.urgency:
        parts.append(" or ".join(u.value.replace("_", " ") for u in query.urgency))
    if query.section:
        parts.append(
            " or ".join(
                "Reading & Writing" if s is Section.reading_writing else "Math"
                for s in query.section
            )
        )
    if query.error_type:
        parts.append(" or ".join(e.value.replace("_", " ") for e in query.error_type))
    if query.topics:
        parts.append("about " + " or ".join(query.topics))
    if query.text:
        parts.append(f"mentioning {query.text!r}")
    if query.logged_after and query.logged_before:
        parts.append(f"logged between {query.logged_after} and {query.logged_before}")
    elif query.logged_after:
        parts.append(f"logged since {query.logged_after}")
    elif query.logged_before:
        parts.append(f"logged before {query.logged_before}")
    if query.only_due:
        parts.append("due for review now")

    return ", ".join(parts) if parts else "everything in the bank"


async def vocabulary(session: AsyncSession, user_id: str) -> Vocabulary:
    """The distinct values in this student's bank, for the model to choose from."""
    topics = await session.scalars(
        select(Mistake.topic)
        .where(Mistake.user_id == user_id, Mistake.topic.is_not(None))
        .distinct()
    )
    sources = await session.scalars(
        select(Mistake.source)
        .where(Mistake.user_id == user_id, Mistake.source.is_not(None))
        .distinct()
    )
    concepts = await session.scalars(
        select(Concept.title).where(Concept.user_id == user_id).distinct()
    )
    return Vocabulary(topics=sorted(topics), concepts=sorted(concepts), sources=sorted(sources))


def overview(mistakes: list[Mistake]) -> str:
    """Counts across the matched rows.

    Questions like "what am I worst at" are answered from these, not by asking the
    model to tally a list by eye - which it will do approximately, and confidently.
    """
    if not mistakes:
        return ""

    def tally(values: list[str]) -> str:
        counts: dict[str, int] = {}
        for value in values:
            counts[value] = counts.get(value, 0) + 1
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return ", ".join(f"{key} ({count})" for key, count in ranked)

    lines = [
        f"By reason: {tally([m.error_type for m in mistakes if m.error_type])}",
        f"By urgency: {tally([m.urgency for m in mistakes if m.urgency])}",
        f"By topic: {tally([m.topic for m in mistakes if m.topic])}",
        f"By section: {tally([m.section for m in mistakes])}",
    ]
    concepts = [concept.title for m in mistakes for concept in m.concepts]
    if concepts:
        lines.append(f"By concept: {tally(concepts)}")
    return "\n".join(lines)


def digest(mistakes: list[Mistake]) -> str:
    """A compact rendering of the results for the model to summarise. Facts only."""
    if not mistakes:
        return "No questions matched."

    lines = [f"{len(mistakes)} question(s) matched.", "", overview(mistakes), "", "Rows:"]
    for index, mistake in enumerate(mistakes, start=1):
        lines.append(
            f"{index}. [{mistake.urgency or 'unrated'}] [{mistake.section}] "
            f"[{mistake.error_type or 'no slot'}] topic={mistake.topic or '-'} "
            f"logged={mistake.created_at.date()} "
            f'question="{mistake.question_text[:120]}" '
            f"you_put={mistake.your_answer!r} answer={mistake.correct_answer!r}"
        )
        if mistake.takeaway:
            lines.append(f"   takeaway: {mistake.takeaway}")
    return "\n".join(lines)
