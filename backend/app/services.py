"""Work that spans the request and the background task."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .analysis import MistakeInput, get_analyzer
from .analysis.base import PatternTag
from .db import get_sessionmaker
from .models import (
    AnalysisStatus,
    Mistake,
    Pattern,
    mistake_options,
    pattern_mistakes,
    pattern_slug,
    utcnow,
)


def to_input(mistake: Mistake, known_patterns: list[str] | None = None) -> MistakeInput:
    return MistakeInput(
        section=mistake.section,
        question_text=mistake.question_text,
        choices=mistake.choices,
        your_answer=mistake.your_answer,
        correct_answer=mistake.correct_answer,
        source=mistake.source,
        student_note=mistake.student_note,
        known_patterns=known_patterns or [],
    )


async def known_pattern_titles(session: AsyncSession, user_id: str) -> list[str]:
    """The patterns already in this bank, commonest first.

    Order matters: the model reads a long list from the top, and the pattern that
    has already collected the most questions is the one most worth reusing.
    """
    rows = await session.execute(
        select(Pattern.title, func.count(pattern_mistakes.c.mistake_id))
        .select_from(Pattern)
        .outerjoin(pattern_mistakes, Pattern.id == pattern_mistakes.c.pattern_id)
        .where(Pattern.user_id == user_id)
        .group_by(Pattern.id, Pattern.title)
        .order_by(func.count(pattern_mistakes.c.mistake_id).desc(), Pattern.title)
    )
    return [title for title, _ in rows]


async def attach_patterns(
    session: AsyncSession, mistake: Mistake, tags: list[PatternTag]
) -> list[Pattern]:
    """Turn the titles the analyzer wrote into rows, reusing what already exists.

    Matching is on the slug, not the title: "Negative-sign slips" and "negative sign
    slips" are one habit, and letting them be two rows is exactly what leaves a bank
    full of patterns with a single question each.

    Replaces this question's patterns rather than adding to them, so re-running a
    debrief corrects its filing instead of piling a second reading on top of the
    first.
    """
    resolved: list[Pattern] = []
    seen: set[str] = set()

    for tag in tags:
        slug = pattern_slug(tag.title)
        if not slug or slug in seen:
            continue
        seen.add(slug)

        pattern = await session.scalar(
            select(Pattern).where(Pattern.user_id == mistake.user_id, Pattern.slug == slug)
        )
        if pattern is None:
            pattern = Pattern(
                user_id=mistake.user_id,
                title=tag.title.strip(),
                slug=slug,
                summary=tag.why.strip() or None,
            )
            session.add(pattern)
        else:
            # An established pattern keeps the wording it collected under; only its
            # recency moves, which is what "what have I been doing lately" reads.
            pattern.last_seen_at = utcnow()
        resolved.append(pattern)

    mistake.patterns = resolved
    await prune_empty_patterns(session, mistake.user_id)
    return resolved


async def prune_empty_patterns(session: AsyncSession, user_id: str) -> int:
    """Delete patterns nothing is filed under any more.

    Re-tagging a question moves it off whatever it was under before, and the row it
    left behind would otherwise sit in the list for ever holding nothing. Worse, it
    stays in the vocabulary handed to the analyzer, which is then invited to reuse a
    name the student has no questions under.
    """
    # Flush first, or the reassignment above is not yet visible to the query and
    # every pattern looks occupied.
    await session.flush()
    orphans = list(
        await session.scalars(
            select(Pattern).where(Pattern.user_id == user_id, ~Pattern.mistakes.any())
        )
    )
    for orphan in orphans:
        await session.delete(orphan)
    return len(orphans)


async def analyze_mistake(session: AsyncSession, mistake: Mistake) -> Mistake:
    """Run the analyzer and write its verdict onto the mistake.

    Never raises for an analyzer failure: a mistake with no analysis is still a
    logged mistake, still on the ladder, and can be re-analyzed later.
    """
    analyzer = get_analyzer()
    known = await known_pattern_titles(session, mistake.user_id)
    try:
        result = await analyzer.analyze(to_input(mistake, known))
    except Exception as exc:  # AnalysisFailed, plus anything a provider SDK throws
        mistake.analysis_status = AnalysisStatus.failed
        mistake.analysis_error = f"{type(exc).__name__}: {exc}"[:1000]
        await session.commit()
        return mistake

    mistake.error_type = result.error_type
    mistake.topic = result.topic
    mistake.difficulty = result.difficulty
    # Never overrule an urgency the student set themselves.
    if not mistake.urgency_is_yours:
        mistake.urgency = result.urgency
    mistake.why_wrong = result.why_wrong
    mistake.correct_reasoning = result.correct_reasoning
    mistake.takeaway = result.takeaway
    mistake.trap = result.trap
    await attach_patterns(session, mistake, result.patterns)
    mistake.analysis_status = AnalysisStatus.ready
    mistake.analysis_error = None
    # A fresh analysis replaces whatever the student wrote, so the edit marker - and
    # the guard it drives - goes with it.
    mistake.analysis_edited_at = None
    mistake.analyzed_at = utcnow()
    mistake.analyzed_by = analyzer.name
    await session.commit()
    return mistake


async def retag_patterns(session: AsyncSession, mistake: Mistake) -> list[Pattern]:
    """Name this question's patterns again, without re-running the whole debrief.

    The backfill path. It asks the analyzer for a fresh reading of a question whose
    analysis already exists, and keeps only the patterns from it - so a bank logged
    before patterns existed can collect them without the debrief the student has
    read (and may have edited) being overwritten underneath them.
    """
    known = await known_pattern_titles(session, mistake.user_id)
    try:
        result = await get_analyzer().analyze(to_input(mistake, known))
    except Exception:
        # One question the model would not read must not abandon the rest of the
        # backfill; the others still get their patterns.
        return list(mistake.patterns)
    return await attach_patterns(session, mistake, result.patterns)


async def analyze_in_background(mistake_id: str) -> None:
    """Background-task entry point. Owns its own session; the request's is long gone."""
    async with get_sessionmaker()() as session:
        mistake = await session.scalar(
            select(Mistake).where(Mistake.id == mistake_id).options(*mistake_options())
        )
        if mistake is None:
            return
        await analyze_mistake(session, mistake)
