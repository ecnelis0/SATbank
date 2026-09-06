"""Runtime configuration, read from the environment (and the repo-root .env)."""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# The repo root .env holds shared secrets; load it before Settings reads the environment.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # SQLAlchemy async URL. sqlite+aiosqlite for local dev, postgresql+asyncpg for Neon.
    database_url: str = "sqlite+aiosqlite:///./sat_bank.db"

    # Which analyzer backs the AI error analysis: "stub" or "claude".
    ai_provider: str = "stub"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
