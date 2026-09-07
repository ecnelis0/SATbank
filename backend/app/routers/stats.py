"""Counts behind the dashboard's slot view."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from ..deps import SessionDep, UserDep
from ..models import Concept, Mistake, ReviewEvent, ReviewOutcome, concept_mistakes, utcnow
from ..schemas import SlotCount, Stats, TopicCount

router = APIRouter(prefix="/stats", tags=["stats"])


async def _grouped(session, user_id: str, column) -> list[SlotCount]:
    rows = await session.execute(
        select(column, func.count())
        .where(Mistake.user_id == user_id, column.is_not(None))
        .group_by(column)
        .order_by(func.count().desc())
    )
    return [SlotCount(key=key, count=count) for key, count in rows]


async def _topics(session, user_id: str) -> list[TopicCount]:
    """Topics grouped under the section they belong to, commonest first."""
    rows = await session.execute(
        select(Mistake.section, Mistake.topic, func.count())
        .where(Mistake.user_id == user_id, Mistake.topic.is_not(None))
        .group_by(Mistake.section, Mistake.topic)
        .order_by(Mistake.section, func.count().desc(), Mistake.topic)
    )
    return [TopicCount(section=section, topic=topic, count=count) for section, topic, count in rows]


async def _concepts(session, user_id: str) -> list[SlotCount]:
    """Concept titles with how many questions are filed under each."""
    rows = await session.execute(
        select(Concept.title, func.count(concept_mistakes.c.mistake_id))
        .select_from(Concept)
        .outerjoin(concept_mistakes, Concept.id == concept_mistakes.c.concept_id)
        .where(Concept.user_id == user_id)
        .group_by(Concept.id, Concept.title)
        .order_by(func.count(concept_mistakes.c.mistake_id).desc(), Concept.title)
    )
    return [SlotCount(key=title, count=count) for title, count in rows]


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
        by_urgency=await _grouped(session, user_id, Mistake.urgency),
        by_concept=await _concepts(session, user_id),
        by_section=await _grouped(session, user_id, Mistake.section),
        topics=await _topics(session, user_id),
    )
