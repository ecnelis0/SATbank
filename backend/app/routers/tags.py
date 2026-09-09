"""The student's own labels.

Deliberately plain strings rather than a table of their own: a tag has no life
beyond the questions carrying it, and the moment you give it an id you owe the
student a way to rename, merge and delete it.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import SessionDep, UserDep
from ..models import SUGGESTED_TAGS, Mistake

router = APIRouter(prefix="/tags", tags=["tags"])


class TagCount(BaseModel):
    tag: str
    count: int
    # True while nothing carries it - a starting suggestion rather than a tag the
    # student has actually chosen to use.
    suggested: bool = False


@router.get("", response_model=list[TagCount])
async def list_tags(session: SessionDep, user_id: UserDep) -> list[TagCount]:
    """Every tag in use, commonest first, then the unused suggestions."""
    rows = await session.scalars(
        select(Mistake.tags).where(Mistake.user_id == user_id, Mistake.tags.is_not(None))
    )

    counts: dict[str, int] = {}
    canonical: dict[str, str] = {}
    for tags in rows:
        for tag in tags or []:
            key = tag.casefold()
            canonical.setdefault(key, tag)
            counts[key] = counts.get(key, 0) + 1

    used = [
        TagCount(tag=canonical[key], count=count)
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    unused = [
        TagCount(tag=tag, count=0, suggested=True)
        for tag in SUGGESTED_TAGS
        if tag.casefold() not in counts
    ]
    return used + unused
