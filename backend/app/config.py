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

    # Explicit production origins. Dev is covered by the regex below instead, because
    # `next dev` silently moves to another port when 3000 is taken - and a browser
    # whose origin is not on the list gets a 400 on preflight and a blank page.
    # Where uploaded pictures land. Outside the repo tree is fine; the path is only
    # ever joined with names the server generated.
    upload_root: str = "./uploads"

    cors_origins: str = ""
    cors_origin_regex: str = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
