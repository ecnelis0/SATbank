"""The side panel's assistant: a question about the bank, answered from the bank."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..ai_choice import current_provider
from ..analysis import get_analyzer
from ..analysis.base import GroupReading
from ..breakdown import group_mistakes
from ..breakdown import render as render_breakdown
from ..commands import is_breakdown_question
from ..config import get_settings
from ..deps import SessionDep, UserDep
from ..query import BankQuery, describe, digest, run_query, vocabulary
from ..readiness import analyzer_ready
from ..schemas import MistakeRead

router = APIRouter(prefix="/ask", tags=["ask"])


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class AskGroup(BaseModel):
    """One reason or pattern the matched questions were lost to."""

    key: str
    kind: str
    label: str
    # Counted by the database, never by the model.
    count: int
    repeat_misses: int
    # The model's reading. None when no model could be reached.
    why: str | None = None
    what_to_do: str | None = None
    mistakes: list[MistakeRead]


class Answer(BaseModel):
    question: str
    answer: str
    # Which analyzer answered, and whether it is the real one. The offline stub
    # returning the whole bank looks identical to a working search that matched
    # everything; this is how the UI can tell the student which they are seeing.
    analyzer: str
    analyzer_ready: bool
    # What was actually searched, so the student can see the assistant's reading of
    # their sentence rather than having to trust it.
    filter_description: str
    query: BankQuery
    mistakes: list[MistakeRead]
    # Set when the question was about where the points are going: the rows
    # grouped by reason and pattern, each with the model's reading of why.
    groups: list[AskGroup] = Field(default_factory=list)
    error: str | None = None


@router.post("", response_model=Answer)
async def ask(body: Ask, session: SessionDep, user_id: UserDep) -> Answer:
    """Answer a question about the bank.

    Three steps, in this order for a reason: the model turns the sentence into a
    filter, the database runs it, and only then does the model get to speak - about
    rows that exist. It never answers from a recollection of the bank.

    A question about *where the points are going* gets a fourth: the matched rows
    grouped by reason and pattern, and each group debriefed (`breakdown.py`).
    """
    settings = get_settings()
    provider = current_provider(settings)
    ready = analyzer_ready(settings)
    breakdown = is_breakdown_question(body.question)

    today = datetime.now(UTC).date()
    # What this bank actually contains, so the model filters on strings that exist.
    words = await vocabulary(session, user_id)

    # `get_analyzer` is inside the try as well: it raises on a provider name it
    # does not know, and a typo in .env should answer with the whole bank rather
    # than a 500.
    error = None
    try:
        query = await get_analyzer().interpret(body.question, today, words)
        interpreted = True
    except Exception as exc:  # a failed interpretation still gets them results
        query = BankQuery()
        interpreted = False
        error = f"{type(exc).__name__}: {exc}"[:500]

    if breakdown:
        # Grouping 25 rows would undercount every group; read as many as allowed.
        query = query.model_copy(update={"limit": 100})
    mistakes = await run_query(session, user_id, query)

    groups: list[AskGroup] = []
    answer = None
    if breakdown:
        found = group_mistakes(mistakes)
        readings: dict[str, GroupReading] = {}
        if found:
            try:
                result = await get_analyzer().explain_breakdown(
                    await render_breakdown(session, body.question, found, mistakes)
                )
                readings = {reading.key: reading for reading in result.groups}
                answer = result.summary
            except Exception as exc:
                # The groups are the database's and stand without the prose.
                error = f"{type(exc).__name__}: {exc}"[:500]
        groups = [
            AskGroup(
                key=group.key,
                kind=group.kind,
                label=group.label,
                count=len(group.mistakes),
                repeat_misses=group.repeat_misses,
                why=readings[group.key].why if group.key in readings else None,
                what_to_do=readings[group.key].what_to_do if group.key in readings else None,
                mistakes=[MistakeRead.model_validate(m) for m in group.mistakes],
            )
            for group in found
        ]

    if answer is None and not interpreted:
        answer = "I could not read that as a search, so here is the whole bank."
    if answer is None:
        try:
            answer = await get_analyzer().summarise(body.question, digest(mistakes))
        except Exception as exc:
            # The rows are the valuable part; losing the prose is survivable.
            answer = f"{len(mistakes)} question(s) matched."
            error = f"{type(exc).__name__}: {exc}"[:500]

    return Answer(
        question=body.question,
        answer=answer,
        analyzer=provider,
        analyzer_ready=ready,
        filter_description=describe(query),
        query=query,
        mistakes=mistakes,
        groups=groups,
        error=error,
    )
