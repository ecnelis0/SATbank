"""The side panel's assistant: a question about the bank, answered from the bank."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..analysis import get_analyzer
from ..deps import SessionDep, UserDep
from ..query import BankQuery, describe, digest, run_query
from ..schemas import MistakeRead

router = APIRouter(prefix="/ask", tags=["ask"])


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class Answer(BaseModel):
    question: str
    answer: str
    # What was actually searched, so the student can see the assistant's reading of
    # their sentence rather than having to trust it.
    filter_description: str
    query: BankQuery
    mistakes: list[MistakeRead]
    error: str | None = None


@router.post("", response_model=Answer)
async def ask(body: Ask, session: SessionDep, user_id: UserDep) -> Answer:
    """Answer a question about the bank.

    Three steps, in this order for a reason: the model turns the sentence into a
    filter, the database runs it, and only then does the model get to speak - about
    rows that exist. It never answers from a recollection of the bank.
    """
    analyzer = get_analyzer()
    today = datetime.now(UTC).date()

    try:
        query = await analyzer.interpret(body.question, today)
    except Exception as exc:  # a failed interpretation still gets them results
        query = BankQuery()
        mistakes = await run_query(session, user_id, query)
        return Answer(
            question=body.question,
            answer="I could not read that as a search, so here is the whole bank.",
            filter_description=describe(query),
            query=query,
            mistakes=mistakes,
            error=f"{type(exc).__name__}: {exc}"[:500],
        )

    mistakes = await run_query(session, user_id, query)

    try:
        answer = await analyzer.summarise(body.question, digest(mistakes))
        error = None
    except Exception as exc:
        # The rows are the valuable part; losing the prose is survivable.
        answer = f"{len(mistakes)} question(s) matched."
        error = f"{type(exc).__name__}: {exc}"[:500]

    return Answer(
        question=body.question,
        answer=answer,
        filter_description=describe(query),
        query=query,
        mistakes=mistakes,
        error=error,
    )
