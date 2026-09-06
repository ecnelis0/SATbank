"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session

# Placeholder identity. Swap for a verified Clerk JWT subject when auth lands; every
# query is already scoped by whatever this returns, so that change stays local.
DEFAULT_USER_ID = "local"


async def current_user_id(x_user_id: Annotated[str | None, Header()] = None) -> str:
    return x_user_id or DEFAULT_USER_ID


SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[str, Depends(current_user_id)]
