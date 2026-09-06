"""FastAPI app: the SAT mistake bank's API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import create_all
from .review import LADDER_LABELS
from .routers import mistakes, reviews, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_all()
    yield


app = FastAPI(title="SAT Mistake Bank", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mistakes.router)
app.include_router(reviews.router)
app.include_router(stats.router)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "analyzer": settings.ai_provider,
        "ladder": list(LADDER_LABELS),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
