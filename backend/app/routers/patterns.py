"""Patterns: the recurring habits the analyzer names, and what they have collected."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..deps import SessionDep, UserDep
from ..models import (
    AnalysisStatus,
    Mistake,
    Pattern,
    mistake_options,
    pattern_mistakes,
)
from ..schemas import PatternDetail, PatternRead
from ..services import retag_patterns

router = APIRouter(prefix="/patterns", tags=["patterns"])


async def _counts(session, user_id: str) -> dict[str, int]:
    rows = await session.execute(
        select(pattern_mistakes.c.pattern_id, func.count())
        .select_from(Pattern)
        .join(pattern_mistakes, Pattern.id == pattern_mistakes.c.pattern_id)
        .where(Pattern.user_id == user_id)
        .group_by(pattern_mistakes.c.pattern_id)
    )
    return {pattern_id: count for pattern_id, count in rows}


async def _ranked(session, user_id: str, min_questions: int = 1) -> list[PatternRead]:
    """The listing itself, as a plain function.

    Separate from the route because `rebuild` wants the same answer, and calling
    the handler would hand it FastAPI's `Query` object instead of an int — which
    is a TypeError at the comparison, not at the call.
    """
    counts = await _counts(session, user_id)
    patterns = await session.scalars(select(Pattern).where(Pattern.user_id == user_id))
    rows = [
        PatternRead(
            id=p.id,
            title=p.title,
            summary=p.summary,
            created_at=p.created_at,
            last_seen_at=p.last_seen_at,
            question_count=counts.get(p.id, 0),
        )
        for p in patterns
    ]
    rows = [row for row in rows if row.question_count >= min_questions]
    rows.sort(key=lambda row: (-row.question_count, row.title))
    return rows


@router.get("", response_model=list[PatternRead])
async def list_patterns(
    session: SessionDep,
    user_id: UserDep,
    min_questions: int = Query(default=1, ge=1, le=100),
) -> list[PatternRead]:
    """Patterns, the ones holding the most questions first.

    That order is the answer to "what do I struggle with most": a pattern with
    nine questions under it is costing more than a pattern with one, whatever
    either of them is about.
    """
    return await _ranked(session, user_id, min_questions)


@router.get("/{pattern_id}", response_model=PatternDetail)
async def get_pattern(pattern_id: str, session: SessionDep, user_id: UserDep) -> PatternDetail:
    pattern = await session.scalar(
        select(Pattern)
        .where(Pattern.id == pattern_id, Pattern.user_id == user_id)
        .options(selectinload(Pattern.mistakes).options(*mistake_options()))
    )
    if pattern is None:
        raise HTTPException(status_code=404, detail="No such pattern")
    return PatternDetail(
        id=pattern.id,
        title=pattern.title,
        summary=pattern.summary,
        created_at=pattern.created_at,
        last_seen_at=pattern.last_seen_at,
        question_count=len(pattern.mistakes),
        mistakes=pattern.mistakes,
    )


@router.post("/rebuild", response_model=list[PatternRead])
async def rebuild(session: SessionDep, user_id: UserDep) -> list[PatternRead]:
    """Run the pattern tagger back over every question that already has a debrief.

    Patterns are only useful once they have collected several questions, and a
    bank logged before this existed would otherwise stay unpatterned until every
    debrief was re-run by hand. Questions are taken oldest first so the earliest
    naming wins and later ones reuse it, which is the same order the bank filled
    in.
    """
    mistakes = list(
        await session.scalars(
            select(Mistake)
            .where(
                Mistake.user_id == user_id,
                Mistake.analysis_status == AnalysisStatus.ready,
            )
            .options(*mistake_options())
            .order_by(Mistake.created_at)
        )
    )
    for mistake in mistakes:
        await retag_patterns(session, mistake)
    await session.commit()
    return await _ranked(session, user_id)
