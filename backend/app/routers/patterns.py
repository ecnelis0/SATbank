"""Patterns: the recurring habits the analyzer names, and what they have collected."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..analysis import get_analyzer
from ..analysis.base import ConceptProposal
from ..deps import SessionDep, UserDep
from ..models import (
    AnalysisStatus,
    Concept,
    Mistake,
    Pattern,
    mistake_options,
    pattern_mistakes,
    utcnow,
)
from ..query import digest
from ..schemas import (
    ConceptDetail,
    ConceptSuggestion,
    PatternCandidate,
    PatternDetail,
    PatternRead,
    PromoteConcept,
)
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


async def _load(session, user_id: str, pattern_id: str) -> Pattern:
    pattern = await session.scalar(
        select(Pattern)
        .where(Pattern.id == pattern_id, Pattern.user_id == user_id)
        .options(selectinload(Pattern.mistakes).options(*mistake_options()))
    )
    if pattern is None:
        raise HTTPException(status_code=404, detail="No such pattern")
    return pattern


@router.get("/{pattern_id}", response_model=PatternDetail)
async def get_pattern(pattern_id: str, session: SessionDep, user_id: UserDep) -> PatternDetail:
    pattern = await _load(session, user_id, pattern_id)
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


# --- a pattern that has collected enough is worth writing up ------------------
#
# The threshold is a judgement, not a law: below it a pattern is a coincidence,
# above it the student is re-learning the same thing a question at a time. Ten is
# where that stops being arguable.

SUGGEST_AT = 10


def _open_for_suggestion(pattern: Pattern) -> bool:
    """Suggest once. A prompt that keeps returning after you have answered it is
    the fastest way to teach someone to ignore prompts."""
    return pattern.promoted_concept_id is None and pattern.dismissed_at is None


@router.get("/suggestions/candidates", response_model=list[PatternCandidate])
async def candidates(
    session: SessionDep,
    user_id: UserDep,
    min_questions: int = Query(default=SUGGEST_AT, ge=2, le=100),
) -> list[PatternCandidate]:
    """Patterns ready to become concepts. Deliberately cheap - no model involved.

    The write-up costs a model call, so it is made when the student opens one,
    not for every candidate on every page load.
    """
    counts = await _counts(session, user_id)
    patterns = await session.scalars(select(Pattern).where(Pattern.user_id == user_id))
    rows = [
        PatternCandidate(
            id=p.id,
            title=p.title,
            summary=p.summary,
            question_count=counts.get(p.id, 0),
        )
        for p in patterns
        if _open_for_suggestion(p) and counts.get(p.id, 0) >= min_questions
    ]
    rows.sort(key=lambda row: (-row.question_count, row.title))
    return rows


@router.post("/{pattern_id}/suggest", response_model=ConceptSuggestion)
async def suggest(pattern_id: str, session: SessionDep, user_id: UserDep) -> ConceptSuggestion:
    """Make the case for this pattern becoming a concept.

    The questions are handed over with their debriefs, so the write-up is drawn
    from what actually happened rather than from the pattern's name.
    """
    pattern = await _load(session, user_id, pattern_id)
    questions = pattern.mistakes

    try:
        proposal = await get_analyzer().propose_concept(
            pattern.title, pattern.summary or "", digest(questions)
        )
        error = None
    except Exception as exc:
        # Still worth showing: the student can write the concept themselves, and
        # the questions it would carry are the valuable part.
        proposal = ConceptProposal(
            title=pattern.title,
            why_a_concept=f"{len(questions)} questions have collected under this.",
            what_went_wrong=pattern.summary or "",
            body="",
        )
        error = f"{type(exc).__name__}: {exc}"[:500]

    return ConceptSuggestion(
        pattern_id=pattern.id,
        pattern_title=pattern.title,
        question_count=len(questions),
        title=proposal.title,
        why_a_concept=proposal.why_a_concept,
        what_went_wrong=proposal.what_went_wrong,
        body=proposal.body,
        mistake_ids=[m.id for m in questions],
        error=error,
    )


@router.post("/{pattern_id}/promote", response_model=ConceptDetail)
async def promote(
    pattern_id: str, body: PromoteConcept, session: SessionDep, user_id: UserDep
) -> ConceptDetail:
    """Write the pattern up as a concept and file every one of its questions under it.

    Tagging them is the point. A concept the student has to attach by hand to
    eleven questions is a concept they will attach to three.
    """
    pattern = await _load(session, user_id, pattern_id)
    if pattern.promoted_concept_id:
        raise HTTPException(status_code=409, detail="That pattern is already a concept")

    concept = Concept(
        user_id=user_id,
        title=(body.title or pattern.title)[:200],
        body=body.body or pattern.summary,
        # Every question under the pattern shares a section often enough to be
        # worth filling in, and nothing at all when they do not.
        section=(
            pattern.mistakes[0].section
            if pattern.mistakes and len({m.section for m in pattern.mistakes}) == 1
            else None
        ),
    )
    concept.mistakes = list(pattern.mistakes)
    session.add(concept)
    await session.flush()

    pattern.promoted_concept_id = concept.id
    await session.commit()

    await session.refresh(concept, ["mistakes", "images"])
    return ConceptDetail(
        id=concept.id,
        created_at=concept.created_at,
        updated_at=concept.updated_at,
        title=concept.title,
        body=concept.body,
        section=concept.section,
        question_count=len(concept.mistakes),
        images=[],
        mistakes=concept.mistakes,
    )


@router.post("/{pattern_id}/dismiss", response_model=PatternRead)
async def dismiss(pattern_id: str, session: SessionDep, user_id: UserDep) -> PatternRead:
    """Not every repeated habit deserves writing up. Saying so has to stick."""
    pattern = await _load(session, user_id, pattern_id)
    pattern.dismissed_at = utcnow()
    await session.commit()
    return PatternRead(
        id=pattern.id,
        title=pattern.title,
        summary=pattern.summary,
        created_at=pattern.created_at,
        last_seen_at=pattern.last_seen_at,
        question_count=len(pattern.mistakes),
    )
