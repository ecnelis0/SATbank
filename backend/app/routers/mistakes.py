"""Logging a wrong question, and browsing the bank."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..deps import SessionDep, UserDep
from ..models import AnalysisStatus, ErrorType, Mistake, Section, utcnow
from ..review import build_ladder
from ..schemas import MistakeCreate, MistakeRead
from ..services import analyze_in_background, analyze_mistake

router = APIRouter(prefix="/mistakes", tags=["mistakes"])


@router.post("", response_model=MistakeRead, status_code=201)
async def log_mistake(
    body: MistakeCreate,
    session: SessionDep,
    user_id: UserDep,
    background: BackgroundTasks,
) -> Mistake:
    """Log a question you got wrong.

    The ladder is armed immediately, anchored to now - a slow or failed analysis must
    never cost the student their 1-hour review.
    """
    logged_at = utcnow()
    mistake = Mistake(
        user_id=user_id,
        created_at=logged_at,
        analysis_status=AnalysisStatus.pending,
        **body.model_dump(),
    )
    mistake.reviews.extend(build_ladder(mistake.id, logged_at))
    session.add(mistake)
    await session.commit()

    background.add_task(analyze_in_background, mistake.id)
    return mistake


@router.get("", response_model=list[MistakeRead])
async def list_mistakes(
    session: SessionDep,
    user_id: UserDep,
    error_type: ErrorType | None = None,
    section: Section | None = None,
    topic: str | None = None,
    status: AnalysisStatus | None = None,
    q: str | None = Query(default=None, description="Substring match on the question text"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Mistake]:
    stmt = (
        select(Mistake)
        .where(Mistake.user_id == user_id)
        .options(selectinload(Mistake.reviews))
        .order_by(Mistake.created_at.desc())
    )
    if error_type is not None:
        stmt = stmt.where(Mistake.error_type == error_type)
    if section is not None:
        stmt = stmt.where(Mistake.section == section)
    if topic is not None:
        stmt = stmt.where(Mistake.topic == topic)
    if status is not None:
        stmt = stmt.where(Mistake.analysis_status == status)
    if q:
        stmt = stmt.where(Mistake.question_text.ilike(f"%{q}%"))

    result = await session.scalars(stmt.limit(limit).offset(offset))
    return list(result)


async def _load(session: SessionDep, user_id: str, mistake_id: str) -> Mistake:
    mistake = await session.scalar(
        select(Mistake)
        .where(Mistake.id == mistake_id, Mistake.user_id == user_id)
        .options(selectinload(Mistake.reviews))
    )
    if mistake is None:
        raise HTTPException(status_code=404, detail="No such mistake")
    return mistake


@router.get("/{mistake_id}", response_model=MistakeRead)
async def get_mistake(mistake_id: str, session: SessionDep, user_id: UserDep) -> Mistake:
    return await _load(session, user_id, mistake_id)


@router.post("/{mistake_id}/reanalyze", response_model=MistakeRead)
async def reanalyze(mistake_id: str, session: SessionDep, user_id: UserDep) -> Mistake:
    """Re-run the analyzer, synchronously, so the caller sees the outcome."""
    mistake = await _load(session, user_id, mistake_id)
    return await analyze_mistake(session, mistake)


@router.delete("/{mistake_id}", status_code=204)
async def delete_mistake(mistake_id: str, session: SessionDep, user_id: UserDep) -> None:
    mistake = await _load(session, user_id, mistake_id)
    await session.delete(mistake)
    await session.commit()
