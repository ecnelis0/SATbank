"""The whole-bank analysis: what you have been doing right and wrong, kept."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from ..analysis import get_analyzer
from ..analysis.base import CoachReport
from ..deps import SessionDep, UserDep
from ..insights import InsightStats, gather, keep_real_ids
from ..models import Insight

router = APIRouter(prefix="/insights", tags=["insights"])


class InsightAsk(BaseModel):
    focus: str | None = Field(default=None, max_length=1000)


class InsightRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    focus: str | None
    analyzer: str
    question_count: int
    stats: InsightStats
    report: CoachReport


@router.get("", response_model=list[InsightRead])
async def list_insights(session: SessionDep, user_id: UserDep) -> list[Insight]:
    return list(
        await session.scalars(
            select(Insight)
            .where(Insight.user_id == user_id)
            .order_by(Insight.created_at.desc())
            .limit(50)
        )
    )


@router.post("", response_model=InsightRead, status_code=201)
async def new_insight(body: InsightAsk, session: SessionDep, user_id: UserDep) -> Insight:
    """Read the bank and write a new analysis. Synchronous: the student is waiting
    on the page for it, and there is nothing useful to show until it is done."""
    gathered = await gather(session, user_id)
    if gathered.stats.questions == 0:
        raise HTTPException(
            status_code=422, detail="Nothing is logged yet, so there is nothing to analyse."
        )

    focus = (body.focus or "").strip() or None
    analyzer = get_analyzer()
    try:
        report = await analyzer.coach(focus, gathered.digest)
    except Exception as exc:
        # Nothing is stored for a failed run: an empty analysis in the history
        # would read as "the AI found nothing", which is not what happened.
        raise HTTPException(
            status_code=502, detail=f"The analysis could not be written: {exc}"[:500]
        ) from exc

    insight = Insight(
        user_id=user_id,
        focus=focus,
        analyzer=analyzer.name,
        question_count=gathered.stats.questions,
        stats=gathered.stats.model_dump(),
        report=keep_real_ids(report, gathered.ids).model_dump(),
    )
    session.add(insight)
    await session.commit()
    return insight


async def _load(session: SessionDep, user_id: str, insight_id: str) -> Insight:
    insight = await session.scalar(
        select(Insight).where(Insight.id == insight_id, Insight.user_id == user_id)
    )
    if insight is None:
        raise HTTPException(status_code=404, detail="No such analysis")
    return insight


@router.get("/{insight_id}", response_model=InsightRead)
async def get_insight(insight_id: str, session: SessionDep, user_id: UserDep) -> Insight:
    return await _load(session, user_id, insight_id)


@router.delete("/{insight_id}", status_code=204)
async def delete_insight(insight_id: str, session: SessionDep, user_id: UserDep) -> None:
    await session.delete(await _load(session, user_id, insight_id))
    await session.commit()
