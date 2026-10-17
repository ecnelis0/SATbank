"""Which AI the app uses, switchable while it runs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..ai_choice import AiChoice, describe, set_provider

router = APIRouter(prefix="/ai", tags=["ai"])


class Switch(BaseModel):
    provider: str


@router.get("", response_model=AiChoice)
async def which_ai() -> AiChoice:
    return describe()


@router.put("", response_model=AiChoice)
async def switch_ai(body: Switch) -> AiChoice:
    """Takes effect on the next call - no restart. Every debrief, scan and chat
    after this goes to the provider chosen here."""
    try:
        set_provider(body.provider)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return describe()
