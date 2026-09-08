"""FastAPI app: the SAT mistake bank's API."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .images import upload_dir
from .migrate import upgrade
from .review import LADDER_LABELS
from .routers import ask, concepts, images, mistakes, reviews, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Migrations, not create_all: the latter cannot add a column to a table that
    # already exists, which is why six schema changes were applied by hand.
    # `upgrade` copies the database aside first if there is anything to apply.
    backup = await asyncio.to_thread(upgrade)
    if backup is not None:
        print(f"Migrated. Backed up first to {backup}")
    yield


app = FastAPI(title="SAT Mistake Bank", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_origin_regex=get_settings().cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Served straight off disk. Only files this server generated names for ever land here.
app.mount(
    "/uploads",
    StaticFiles(directory=upload_dir(get_settings().upload_root)),
    name="uploads",
)

app.include_router(mistakes.router)
app.include_router(reviews.router)
app.include_router(stats.router)
app.include_router(images.router)
app.include_router(concepts.router)
app.include_router(ask.router)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Says which analyzer is running and whether it can actually be used.

    `analyzer_ready` is false when a provider is selected but its key is missing -
    the difference between "the AI is off" and "the AI is misconfigured", which is
    otherwise only discoverable by watching an analysis fail.
    """
    settings = get_settings()
    provider = settings.ai_provider.lower()
    ready = provider == "stub" or (provider == "claude" and bool(settings.anthropic_api_key))

    return {
        "status": "ok",
        "analyzer": settings.ai_provider,
        "analyzer_ready": ready,
        "model": settings.anthropic_model if provider == "claude" else None,
        "ladder": list(LADDER_LABELS),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
