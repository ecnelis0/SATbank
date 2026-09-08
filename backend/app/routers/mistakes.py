"""Logging a wrong question, and browsing the bank."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from sqlalchemy import select

from ..config import get_settings
from ..deps import SessionDep, UserDep
from ..images import delete as delete_file
from ..models import (
    AnalysisStatus,
    ErrorType,
    Mistake,
    Section,
    Urgency,
    blank_collections,
    mistake_options,
    utcnow,
)
from ..query import BankQuery, run_query, text_filter
from ..review import build_ladder
from ..schemas import MistakeCreate, MistakeRead, MistakeUpdate
from ..services import analyze_in_background, analyze_mistake

router = APIRouter(prefix="/mistakes", tags=["mistakes"])


@router.post("", response_model=MistakeRead, status_code=201)
async def log_mistake(
    body: MistakeCreate,
    session: SessionDep,
    user_id: UserDep,
    background: BackgroundTasks,
    analyze: bool = Query(
        default=True,
        description="Ask the AI now. False logs the question and waits to be asked.",
    ),
) -> Mistake:
    """Log a question you got wrong.

    The ladder is armed immediately, anchored to now - a slow, failed, or unasked-for
    analysis must never cost the student their 1-hour review.
    """
    logged_at = utcnow()
    mistake = Mistake(
        user_id=user_id,
        created_at=logged_at,
        analysis_status=AnalysisStatus.pending if analyze else AnalysisStatus.not_requested,
        **body.model_dump(),
    )
    mistake.reviews.extend(build_ladder(mistake.id, logged_at))
    blank_collections(mistake)
    session.add(mistake)
    await session.commit()

    if analyze:
        background.add_task(analyze_in_background, mistake.id)
    return mistake


@router.get("", response_model=list[MistakeRead])
async def list_mistakes(
    session: SessionDep,
    user_id: UserDep,
    error_type: ErrorType | None = None,
    urgency: Urgency | None = None,
    section: Section | None = None,
    topic: str | None = None,
    status: AnalysisStatus | None = None,
    q: str | None = Query(
        default=None,
        description="Words to find. Every word must appear somewhere on the question - "
        "its text, source, answers, note, topic or analysis.",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Mistake]:
    stmt = (
        select(Mistake)
        .where(Mistake.user_id == user_id)
        .options(*mistake_options())
        .order_by(Mistake.created_at.desc())
    )
    if error_type is not None:
        stmt = stmt.where(Mistake.error_type == error_type)
    if urgency is not None:
        stmt = stmt.where(Mistake.urgency == urgency)
    if section is not None:
        stmt = stmt.where(Mistake.section == section)
    if topic is not None:
        stmt = stmt.where(Mistake.topic == topic)
    if status is not None:
        stmt = stmt.where(Mistake.analysis_status == status)
    if q:
        # The same matcher the bank and the assistant use, so a search means the
        # same thing wherever it is typed.
        clause = text_filter(q)
        if clause is not None:
            stmt = stmt.where(clause)

    result = await session.scalars(stmt.limit(limit).offset(offset))
    return list(result)


async def _load(session: SessionDep, user_id: str, mistake_id: str) -> Mistake:
    mistake = await session.scalar(
        select(Mistake)
        .where(Mistake.id == mistake_id, Mistake.user_id == user_id)
        .options(*mistake_options())
    )
    if mistake is None:
        raise HTTPException(status_code=404, detail="No such mistake")
    return mistake


@router.post("/search", response_model=list[MistakeRead])
async def search(body: BankQuery, session: SessionDep, user_id: UserDep) -> list[Mistake]:
    """Filter the bank by any combination of facets.

    A POST because the filter is a structure, not a handful of scalars: each facet
    takes a list, OR within a list and AND across them. The same `BankQuery` the
    assistant produces, so the panel and the bank page cannot drift apart.
    """
    return await run_query(session, user_id, body)


@router.get("/{mistake_id}", response_model=MistakeRead)
async def get_mistake(mistake_id: str, session: SessionDep, user_id: UserDep) -> Mistake:
    return await _load(session, user_id, mistake_id)


@router.patch("/{mistake_id}", response_model=MistakeRead)
async def update_mistake(
    mistake_id: str,
    body: MistakeUpdate,
    session: SessionDep,
    user_id: UserDep,
) -> Mistake:
    """Edit any field, the AI's included. Only the keys sent are changed."""
    mistake = await _load(session, user_id, mistake_id)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(mistake, field, value)

    if body.touches_analysis():
        mistake.analysis_edited_at = utcnow()
        # Hand-written analysis counts as analysis: it should read, group and filter
        # exactly like the AI's, and the question should stop asking to be analysed.
        if mistake.analysis_status != AnalysisStatus.ready:
            mistake.analysis_status = AnalysisStatus.ready
            mistake.analysis_error = None
        if mistake.analyzed_by is None:
            mistake.analyzed_by = "you"

    await session.commit()
    return mistake


@router.post("/{mistake_id}/analyze", response_model=MistakeRead)
async def analyze(
    mistake_id: str,
    session: SessionDep,
    user_id: UserDep,
    force: bool = Query(
        default=False, description="Required to overwrite an analysis you have edited."
    ),
) -> Mistake:
    """Ask the AI to debrief this question, synchronously, so the caller sees the result.

    Covers the first run for a hand-logged question and a re-run for one that failed.
    """
    mistake = await _load(session, user_id, mistake_id)

    if mistake.analysis_edited_at is not None and not force:
        raise HTTPException(
            status_code=409,
            detail="You have edited this analysis. Re-run with force=true to replace it.",
        )

    return await analyze_mistake(session, mistake)


@router.delete("/{mistake_id}", status_code=204)
async def delete_mistake(mistake_id: str, session: SessionDep, user_id: UserDep) -> None:
    """Deletes the question, its ladder, and the bytes of its pictures.

    The image rows cascade; the files on disk do not, so without this every deleted
    question leaves its pictures behind forever.
    """
    mistake = await _load(session, user_id, mistake_id)
    filenames = [image.filename for image in mistake.images]

    await session.delete(mistake)
    await session.commit()

    root = get_settings().upload_root
    for filename in filenames:
        delete_file(filename, root)
