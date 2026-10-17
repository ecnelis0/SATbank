"""Analyzer selection. `AI_PROVIDER` decides which one the app runs with."""

from __future__ import annotations

from functools import lru_cache

from ..ai_choice import current_provider
from ..config import get_settings
from .base import AnalysisFailed, Analyzer, MistakeAnalysis, MistakeInput, Turn
from .guard import Guarded
from .stub import StubAnalyzer

__all__ = [
    "AnalysisFailed",
    "Analyzer",
    "MistakeAnalysis",
    "MistakeInput",
    "StubAnalyzer",
    "Turn",
    "get_analyzer",
]


def get_analyzer() -> Analyzer:
    """The analyzer in charge right now, with a time limit around it.

    Resolved on every call, because the student can switch providers while the
    app runs (`ai_choice.py`). Building one is cached per provider, so flipping
    back and forth does not open a new client each time.
    """
    return _build(current_provider())


@lru_cache
def _build(provider: str) -> Analyzer:
    """The limit is not applied to the stub: it does no I/O, so it cannot hang,
    and wrapping it would only put a proxy between the tests and the thing they
    are asserting on.
    """
    settings = get_settings()

    if provider == "stub":
        return StubAnalyzer()

    if provider == "claude":
        # Imported lazily so the stub path never needs the anthropic package configured.
        from .claude import ClaudeAnalyzer

        return Guarded(
            ClaudeAnalyzer(settings.anthropic_api_key, settings.anthropic_model),
            settings.ai_timeout_seconds,
        )

    if provider == "openai":
        from .openai_provider import OpenAIAnalyzer

        return Guarded(
            OpenAIAnalyzer(settings.openai_api_key, settings.openai_model),
            settings.ai_timeout_seconds,
        )

    if provider == "agent":
        # Claude Agent SDK: drives the Claude Code CLI, paid for by the plan you
        # are logged into with `claude auth login`. No API key.
        from .agent import AgentAnalyzer

        return Guarded(AgentAnalyzer(settings.anthropic_model), settings.ai_timeout_seconds)

    raise ValueError(
        f"Unknown AI_PROVIDER {provider!r}; "
        "expected 'stub', 'claude', 'openai' or 'agent'"
    )


# The tests reset the cache between runs by this name; it predates the switch.
get_analyzer.cache_clear = _build.cache_clear  # type: ignore[attr-defined]
