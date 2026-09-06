from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

# Set before anything imports app.config, so no developer's real .env can point the
# test suite at a live database or a paid analyzer.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./__test__.db"
os.environ["AI_PROVIDER"] = "stub"


@pytest.fixture
async def app_env(tmp_path, monkeypatch):
    """A fresh database file and fresh module-level caches for each test."""
    from app import config, db
    from app.analysis import get_analyzer

    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("AI_PROVIDER", "stub")
    config.get_settings.cache_clear()
    get_analyzer.cache_clear()
    db._engine = None
    db._sessionmaker = None

    await db.create_all()
    yield db

    await db.get_engine().dispose()
    config.get_settings.cache_clear()
    get_analyzer.cache_clear()
    db._engine = None
    db._sessionmaker = None


@pytest.fixture
async def client(app_env):
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def session_factory(app_env):
    return app_env.get_sessionmaker()


MATH_MISTAKE = {
    "section": "math",
    "source": "Bluebook Practice Test 4",
    "question_text": "If 3x + 7 = 22, what is the value of x?",
    "choices": ["3", "5", "7", "15"],
    "your_answer": "7",
    "correct_answer": "5",
    "student_note": "I subtracted wrong under time pressure.",
}

VERBAL_MISTAKE = {
    "section": "reading_writing",
    "question_text": "Which choice provides the best evidence for the previous answer?",
    "choices": ["Lines 4-6", "Lines 12-14", "Lines 20-22", "Lines 31-33"],
    "your_answer": "Lines 4-6",
    "correct_answer": "Lines 20-22",
}
