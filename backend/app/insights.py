"""What the whole-bank analysis reads, and the numbers that sit beside it.

The same rule as everywhere else: the database counts and the model writes. Every
number in `InsightStats` is tallied here from rows, handed to the model as fact,
and shown on screen next to its prose - so a count the model got wrong would sit
beside the right one rather than replace it.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .analysis.base import CoachReport
from .models import AnalysisStatus, DebriefTurn, Mistake, ReviewOutcome, mistake_options
from .report import ERROR_TYPE_LABELS, SECTION_LABELS

# The most recent questions read at once. A whole bank of hundreds in one prompt
# is slower, dearer and worse - attention is finite, and last term's misses say
# less about now than last week's.
INSIGHT_LIMIT = 150


class Count(BaseModel):
    label: str
    count: int


class InsightStats(BaseModel):
    questions: int
    debriefed: int
    talked_to: int
    reviews_right: int
    reviews_wrong: int
    by_reason: list[Count]
    by_section: list[Count]
    top_patterns: list[Count]


class Gathered(BaseModel):
    stats: InsightStats
    digest: str
    ids: list[str]


def _ranked(counter: Counter[str], limit: int | None = None) -> list[Count]:
    ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return [Count(label=label, count=count) for label, count in ordered[:limit]]


def _clip(text: str | None, limit: int) -> str:
    flat = " ".join((text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


async def gather(session: AsyncSession, user_id: str) -> Gathered:
    mistakes = list(
        await session.scalars(
            select(Mistake)
            .where(Mistake.user_id == user_id)
            .options(*mistake_options())
            .order_by(Mistake.created_at.desc())
            .limit(INSIGHT_LIMIT)
        )
    )
    ids = [m.id for m in mistakes]

    said: dict[str, list[str]] = {}
    if ids:
        rows = await session.execute(
            select(DebriefTurn.mistake_id, DebriefTurn.text)
            .where(DebriefTurn.mistake_id.in_(ids), DebriefTurn.role == "student")
            .order_by(DebriefTurn.created_at)
        )
        for mistake_id, text in rows:
            said.setdefault(mistake_id, []).append(text)

    right = wrong = 0
    reasons: Counter[str] = Counter()
    sections: Counter[str] = Counter()
    patterns: Counter[str] = Counter()
    for mistake in mistakes:
        sections[SECTION_LABELS.get(mistake.section, mistake.section)] += 1
        if mistake.error_type:
            reasons[ERROR_TYPE_LABELS.get(mistake.error_type, mistake.error_type)] += 1
        for pattern in mistake.patterns:
            patterns[pattern.title] += 1
        for review in mistake.reviews:
            if review.outcome == ReviewOutcome.correct:
                right += 1
            elif review.outcome == ReviewOutcome.wrong:
                wrong += 1

    stats = InsightStats(
        questions=len(mistakes),
        debriefed=sum(1 for m in mistakes if m.analysis_status == AnalysisStatus.ready),
        talked_to=len(said),
        reviews_right=right,
        reviews_wrong=wrong,
        by_reason=_ranked(reasons),
        by_section=_ranked(sections),
        top_patterns=_ranked(patterns, 8),
    )
    return Gathered(stats=stats, digest=_render(stats, mistakes, said), ids=ids)


def _render(stats: InsightStats, mistakes: list[Mistake], said: dict[str, list[str]]) -> str:
    def listed(counts: list[Count]) -> str:
        return ", ".join(f"{c.label} ({c.count})" for c in counts) or "-"

    lines = [
        "Counts, made by the database - quote these, do not recompute them:",
        f"Questions read: {stats.questions} (most recent first; {stats.debriefed} debriefed, "
        f"{stats.talked_to} the student talked to the debrief about)",
        f"Reviews: {stats.reviews_right} answered right, {stats.reviews_wrong} still wrong",
        f"By reason: {listed(stats.by_reason)}",
        f"By section: {listed(stats.by_section)}",
        f"Most common patterns: {listed(stats.top_patterns)}",
        "",
        "The questions:",
    ]
    for m in mistakes:
        outcomes = [
            r.outcome
            for r in m.reviews
            if r.outcome in (ReviewOutcome.correct, ReviewOutcome.wrong)
        ]
        latest = outcomes[-1] if outcomes else None
        lines.append(
            f"id={m.id} logged={m.created_at.date()} [{m.section}] "
            f"reason={m.error_type or '-'} topic={m.topic or '-'} urgency={m.urgency or '-'}"
        )
        lines.append(
            f'   question="{_clip(m.question_text, 160)}" '
            f"you_put={_clip(m.your_answer, 60)!r} answer={_clip(m.correct_answer, 60)!r}"
        )
        if m.student_note:
            lines.append(f"   what happened, in their words: {_clip(m.student_note, 300)}")
        if m.headline:
            lines.append(f"   debrief: {_clip(m.headline, 200)}")
        if m.takeaway:
            lines.append(f"   takeaway: {_clip(m.takeaway, 200)}")
        if m.patterns:
            lines.append(f"   patterns: {'; '.join(p.title for p in m.patterns)}")
        if outcomes:
            lines.append(
                f"   reviews: right {outcomes.count(ReviewOutcome.correct)}, "
                f"wrong {outcomes.count(ReviewOutcome.wrong)}, latest {latest}"
            )
        for text in said.get(m.id, [])[-3:]:
            lines.append(f"   they told the debrief: {_clip(text, 300)}")
    return "\n".join(lines)


def keep_real_ids(report: CoachReport, ids: list[str]) -> CoachReport:
    """Drop any question id the model cited that is not one it was shown.

    A link to a question that does not exist is a broken promise on screen; a
    point with one fewer citation is still a true point.
    """
    known = set(ids)
    for point in [*report.doing_well, *report.going_wrong]:
        point.question_ids = [i for i in dict.fromkeys(point.question_ids) if i in known]
    return report
