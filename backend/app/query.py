"""Structured queries over the bank.

The assistant does not answer from memory or from a blob of context. It turns a
question into one of these, the database answers it, and only then does the model
get to say anything - so a count is a count and a list is the real list.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Concept,
    ErrorType,
    Mistake,
    ReviewEvent,
    ReviewOutcome,
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

    tags: list[str] = Field(
        default_factory=list,
        description="The student's own labels, e.g. 'by mistake'. Matched exactly, ignoring case.",
    )
    topics: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)

    def render(self) -> str:
        def block(title: str, values: list[str]) -> str:
            return f"{title}: {', '.join(values) if values else '(none yet)'}"

        return "\n".join(
            [
                block("Topics in this bank", self.topics),
                block("Tags the student uses", self.tags),
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
    tags: list[str] = Field(
        default_factory=list,
        description="The student's own labels, copied from the tags you were given, "
        "e.g. 'by mistake'. Matched exactly, ignoring case.",
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
    has_concept: bool | None = Field(
        default=None,
        description="True for questions filed under some concept, False for the ones "
        "filed under none. Leave unset for both.",
    )
    sort: Sort = "newest"
    limit: int = Field(default=25, ge=1, le=100)


# What a text search looks at. The question alone is not enough: people search for
# where a question came from ("Bluebook"), for an answer ("36"), or for the topic.
SEARCHABLE = (
    Mistake.question_text,
    Mistake.source,
    Mistake.your_answer,
    Mistake.correct_answer,
    Mistake.student_note,
    Mistake.topic,
    Mistake.why_wrong,
    Mistake.takeaway,
)


def text_filter(term: str):
    """Every word must appear somewhere; each word may appear in any field.

    So "area circle" finds a question about the area of a circle even though those
    two words never sit next to each other - which a single LIKE '%area circle%'
    cannot do, and which is how the old search returned nothing for most phrases.
    """
    words = [word for word in term.split() if word]
    if not words:
        return None
    return and_(*[or_(*[column.ilike(f"%{word}%") for column in SEARCHABLE]) for word in words])


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
    if query.tags:
        # tags is a JSON array, so this is a substring match on the serialised list.
        # Quoted to stop "guessed" matching a tag that merely contains it.
        stmt = stmt.where(
            or_(*[Mistake.tags.cast(String).ilike(f'%"{tag}"%') for tag in query.tags])
        )
    if query.topics:
        stmt = stmt.where(or_(*[Mistake.topic.ilike(f"%{topic}%") for topic in query.topics]))
    if query.text:
        clause = text_filter(query.text)
        if clause is not None:
            stmt = stmt.where(clause)
    if query.logged_after:
        stmt = stmt.where(
            Mistake.created_at >= datetime.combine(query.logged_after, time.min, tzinfo=UTC)
        )
    if query.logged_before:
        stmt = stmt.where(
            Mistake.created_at <= datetime.combine(query.logged_before, time.max, tzinfo=UTC)
        )
    if query.has_concept is not None:
        tagged = Mistake.concepts.any()
        stmt = stmt.where(tagged if query.has_concept else ~tagged)
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
    if query.tags:
        parts.append("tagged " + " or ".join(query.tags))
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
    if query.has_concept is True:
        parts.append("filed under a concept")
    elif query.has_concept is False:
        parts.append("not filed under any concept")
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
    tag_rows = await session.scalars(
        select(Mistake.tags).where(Mistake.user_id == user_id, Mistake.tags.is_not(None))
    )
    tags = sorted({tag for row in tag_rows for tag in (row or [])})
    return Vocabulary(
        topics=sorted(topics),
        concepts=sorted(concepts),
        sources=sorted(sources),
        tags=tags,
    )


def times_missed_again(mistake: Mistake) -> int:
    """How many times this question was still wrong when it came back.

    The number that separates "I slipped once" from "I do not know this". A review
    answered `wrong` is a genuine repeat miss; `superseded` rungs are bookkeeping
    from the restart that miss caused, and counting them would inflate every total.
    """
    return sum(1 for review in mistake.reviews if review.outcome == ReviewOutcome.wrong)


def _rank(pairs: list[tuple[str, int]]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for key, n in pairs:
        counts[key] = counts.get(key, 0) + n
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def recurring(mistakes: list[Mistake]) -> str:
    """What the student keeps getting wrong.

    Two different things count, and reporting only one of them was a real gap:

    * **Breadth** - several *different* questions missed in the same area. Four
      different inverse trig questions, each wrong once, is a weakness in inverse
      trig even though no single question has ever come back.
    * **Repetition** - the same question still wrong when it came round again.

    Both answer "what do I consistently get wrong"; neither answers it alone.
    """
    lines: list[str] = []

    def spread(label: str, pairs: list[tuple[str, int]]) -> None:
        areas = [(key, n) for key, n in _rank(pairs) if n > 1]
        if areas:
            lines.append(
                f"{label}: " + ", ".join(f"{key} ({n} different questions)" for key, n in areas)
            )

    spread(
        "Topics missed across several different questions",
        [(m.topic, 1) for m in mistakes if m.topic],
    )
    spread(
        "Concepts missed across several different questions",
        [(c.title, 1) for m in mistakes for c in m.concepts],
    )
    spread(
        "Reasons behind several different questions",
        [(m.error_type, 1) for m in mistakes if m.error_type],
    )

    if not lines:
        lines.append("No topic, concept or reason accounts for more than one question yet.")

    repeats = [(m, times_missed_again(m)) for m in mistakes]
    repeated = [(m, n) for m, n in repeats if n > 0]
    if not repeated:
        lines.append("Nothing here has been missed again on review.")
        return "\n".join(lines)

    lines.append(
        f"{len(repeated)} question(s) have also been missed again on review, "
        f"{sum(n for _, n in repeated)} time(s) in total."
    )

    def again(label: str, pairs: list[tuple[str, int]]) -> None:
        if pairs:
            lines.append(
                f"{label}: "
                + ", ".join(
                    f"{key} ({n} repeat miss{'es' if n > 1 else ''})" for key, n in _rank(pairs)
                )
            )

    again("Topics that keep coming back", [(m.topic, n) for m, n in repeated if m.topic])
    again(
        "Reasons that keep coming back",
        [(m.error_type, n) for m, n in repeated if m.error_type],
    )
    again(
        "Concepts that keep coming back",
        [(c.title, n) for m, n in repeated for c in m.concepts],
    )
    worst = sorted(repeated, key=lambda pair: -pair[1])[:5]
    lines.append(
        "Worst offenders: " + "; ".join(f'"{m.question_text[:60]}" ({n}x)' for m, n in worst)
    )
    return "\n".join(lines)


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
    lines.append("")
    lines.append(recurring(mistakes))
    return "\n".join(lines)


def digest(mistakes: list[Mistake]) -> str:
    """A compact rendering of the results for the model to summarise. Facts only."""
    if not mistakes:
        return "No questions matched."

    lines = [f"{len(mistakes)} question(s) matched.", "", overview(mistakes), "", "Rows:"]
    for index, mistake in enumerate(mistakes, start=1):
        repeats = times_missed_again(mistake)
        concepts = ", ".join(concept.title for concept in mistake.concepts) or "-"
        lines.append(
            f"{index}. [{mistake.urgency or 'unrated'}] [{mistake.section}] "
            f"[{mistake.error_type or 'no slot'}] topic={mistake.topic or '-'} "
            f"concepts={concepts} logged={mistake.created_at.date()} "
            f"missed_again_on_review={repeats} "
            f'question="{mistake.question_text[:120]}" '
            f"you_put={mistake.your_answer!r} answer={mistake.correct_answer!r}"
        )
        if mistake.takeaway:
            lines.append(f"   takeaway: {mistake.takeaway}")
    return "\n".join(lines)
