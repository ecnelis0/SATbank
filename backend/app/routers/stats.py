"""Counts behind the dashboard's slot view."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from ..deps import SessionDep, UserDep
from ..models import Mistake, ReviewEvent, ReviewOutcome, utcnow
from ..schemas import SlotCount, Stats

router = APIRouter(prefix="/stats", tags=["stats"])


async def _grouped(session, user_id: str, column) -> list[SlotCount]:
    rows = await session.execute(
        select(column, func.count())
        .where(Mistake.user_id == user_id, column.is_not(None))
        .group_by(column)
        .order_by(func.count().desc())
    )
    return [SlotCount(key=key, count=count) for key, count in rows]


@router.get("", response_model=Stats)
async def stats(session: SessionDep, user_id: UserDep) -> Stats:
    total = await session.scalar(
        select(func.count()).select_from(Mistake).where(Mistake.user_id == user_id)
    )
    due = await session.scalar(
        select(func.count())
        .select_from(ReviewEvent)
        .join(Mistake)
        .where(
            Mistake.user_id == user_id,
            ReviewEvent.completed_at.is_(None),
            ReviewEvent.due_at <= utcnow(),
        )
    )
    completed = await session.scalar(
        select(func.count())
        .select_from(ReviewEvent)
        .join(Mistake)
        .where(
            Mistake.user_id == user_id,
            ReviewEvent.completed_at.is_not(None),
            ReviewEvent.outcome != ReviewOutcome.superseded,
        )
    )
    return Stats(
        total_mistakes=total or 0,
        due_now=due or 0,
        reviews_completed=completed or 0,
        by_error_type=await _grouped(session, user_id, Mistake.error_type),
        by_topic=await _grouped(session, user_id, Mistake.topic),
        by_section=await _grouped(session, user_id, Mistake.section),
    )
