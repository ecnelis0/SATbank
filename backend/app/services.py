"""Work that spans the request and the background task."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .analysis import MistakeInput, get_analyzer
from .db import get_sessionmaker
from .models import AnalysisStatus, Mistake, utcnow


def to_input(mistake: Mistake) -> MistakeInput:
    return MistakeInput(
        section=mistake.section,
        question_text=mistake.question_text,
        choices=mistake.choices,
        your_answer=mistake.your_answer,
        correct_answer=mistake.correct_answer,
        source=mistake.source,
        student_note=mistake.student_note,
    )


async def analyze_mistake(session: AsyncSession, mistake: Mistake) -> Mistake:
    """Run the analyzer and write its verdict onto the mistake.

    Never raises for an analyzer failure: a mistake with no analysis is still a
    logged mistake, still on the ladder, and can be re-analyzed later.
    """
    analyzer = get_analyzer()
    try:
        result = await analyzer.analyze(to_input(mistake))
    except Exception as exc:  # AnalysisFailed, plus anything a provider SDK throws
        mistake.analysis_status = AnalysisStatus.failed
        mistake.analysis_error = f"{type(exc).__name__}: {exc}"[:1000]
        await session.commit()
        return mistake

    mistake.error_type = result.error_type
    mistake.topic = result.topic
    mistake.difficulty = result.difficulty
    mistake.urgency = result.urgency
    mistake.why_wrong = result.why_wrong
    mistake.correct_reasoning = result.correct_reasoning
    mistake.takeaway = result.takeaway
    mistake.trap = result.trap
    mistake.tags = result.tags
    mistake.analysis_status = AnalysisStatus.ready
    mistake.analysis_error = None
    # A fresh analysis replaces whatever the student wrote, so the edit marker - and
    # the guard it drives - goes with it.
    mistake.analysis_edited_at = None
    mistake.analyzed_at = utcnow()
    mistake.analyzed_by = analyzer.name
    await session.commit()
    return mistake


async def analyze_in_background(mistake_id: str) -> None:
    """Background-task entry point. Owns its own session; the request's is long gone."""
    async with get_sessionmaker()() as session:
        mistake = await session.scalar(
            select(Mistake).where(Mistake.id == mistake_id).options(selectinload(Mistake.reviews))
        )
        if mistake is None:
            return
        await analyze_mistake(session, mistake)
