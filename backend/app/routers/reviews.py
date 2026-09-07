"""The review queue: what is due now, what is coming, and marking a rung done."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..deps import SessionDep, UserDep
from ..models import Mistake, ReviewEvent, ReviewOutcome, mistake_options, utcnow
from ..review import URGENCY_RANK, restart_ladder
from ..schemas import DueReview, ReviewComplete, ReviewCompleteResult

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _open_for_user(user_id: str):
    return (
        select(ReviewEvent)
        .join(Mistake)
        .where(Mistake.user_id == user_id, ReviewEvent.completed_at.is_(None))
        .options(selectinload(ReviewEvent.mistake).options(*mistake_options()))
    )


@router.get("/due", response_model=list[DueReview])
async def due_now(
    session: SessionDep,
    user_id: UserDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[DueReview]:
    """Rungs whose time has come, most urgent first, then oldest.

    Everything here is already due, so the question to put in front of the student
    is the one that matters most - not merely the one that ripened first.
    """
    stmt = (
        _open_for_user(user_id)
        .where(ReviewEvent.due_at <= utcnow())
        .order_by(URGENCY_RANK, ReviewEvent.due_at)
        .limit(limit)
    )
    events = await session.scalars(stmt)
    return [DueReview(review=e, mistake=e.mistake) for e in events]


@router.get("/upcoming", response_model=list[DueReview])
async def upcoming(
    session: SessionDep,
    user_id: UserDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[DueReview]:
    stmt = (
        _open_for_user(user_id)
        .where(ReviewEvent.due_at > utcnow())
        .order_by(ReviewEvent.due_at)
        .limit(limit)
    )
    events = await session.scalars(stmt)
    return [DueReview(review=e, mistake=e.mistake) for e in events]


@router.post("/{review_id}/complete", response_model=ReviewCompleteResult)
async def complete(
    review_id: str,
    body: ReviewComplete,
    session: SessionDep,
    user_id: UserDep,
) -> ReviewCompleteResult:
    """Record how the review went.

    Getting it right or skipping leaves the rest of the ladder alone. Getting it wrong
    again restarts the ladder from now - see `app/review.py`.
    """
    event = await session.scalar(
        select(ReviewEvent)
        .join(Mistake)
        .where(ReviewEvent.id == review_id, Mistake.user_id == user_id)
        .options(selectinload(ReviewEvent.mistake).options(*mistake_options()))
    )
    if event is None:
        raise HTTPException(status_code=404, detail="No such review")
    if event.completed_at is not None:
        raise HTTPException(status_code=409, detail="That review is already completed")

    event.completed_at = utcnow()
    event.outcome = body.outcome

    restarted = body.outcome is ReviewOutcome.wrong
    if restarted:
        restart_ladder(event.mistake)

    await session.commit()

    remaining = [e.due_at for e in event.mistake.reviews if e.completed_at is None]
    return ReviewCompleteResult(
        review=event,
        ladder_restarted=restarted,
        next_due_at=min(remaining, default=None),
    )
