"""Analyzer selection. `AI_PROVIDER` decides which one the app runs with."""

from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from .base import AnalysisFailed, Analyzer, MistakeAnalysis, MistakeInput
from .stub import StubAnalyzer

__all__ = [
    "AnalysisFailed",
    "Analyzer",
    "MistakeAnalysis",
    "MistakeInput",
    "StubAnalyzer",
    "get_analyzer",
]


@lru_cache
def get_analyzer() -> Analyzer:
    settings = get_settings()
    provider = settings.ai_provider.lower()

    if provider == "stub":
        return StubAnalyzer()

    if provider == "claude":
        # Imported lazily so the stub path never needs the anthropic package configured.
        from .claude import ClaudeAnalyzer

        return ClaudeAnalyzer(settings.anthropic_api_key, settings.anthropic_model)

    raise ValueError(f"Unknown AI_PROVIDER {settings.ai_provider!r}; expected 'stub' or 'claude'")
