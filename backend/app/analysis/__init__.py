"""Analyzer selection. `AI_PROVIDER` decides which one the app runs with."""

from __future__ import annotations

from functools import lru_cache

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


@lru_cache
def get_analyzer() -> Analyzer:
    """The configured analyzer, with a time limit around it.

    The limit is not applied to the stub: it does no I/O, so it cannot hang, and
    wrapping it would only put a proxy between the tests and the thing they are
    asserting on.
    """
    settings = get_settings()
    provider = settings.ai_provider.lower()

    if provider == "stub":
        return StubAnalyzer()

    if provider == "claude":
        # Imported lazily so the stub path never needs the anthropic package configured.
        from .claude import ClaudeAnalyzer

        return Guarded(
            ClaudeAnalyzer(settings.anthropic_api_key, settings.anthropic_model),
            settings.ai_timeout_seconds,
        )

    if provider == "agent":
        # Claude Agent SDK: drives the Claude Code CLI, paid for by the plan you
        # are logged into with `claude auth login`. No API key.
        from .agent import AgentAnalyzer

        return Guarded(AgentAnalyzer(settings.anthropic_model), settings.ai_timeout_seconds)

    raise ValueError(
        f"Unknown AI_PROVIDER {settings.ai_provider!r}; expected 'stub', 'claude' or 'agent'"
    )
