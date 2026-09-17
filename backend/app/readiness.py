"""Is the configured analyzer actually usable?

One definition, in one place. It used to be written out separately in `/health`
and in `/ask`, which is exactly how they came to disagree: the agent provider
has a CLI login rather than an API key, so the key check that `/ask` still did
reported "not configured" while `/health`, and the analyzer itself, were fine.
"""

from __future__ import annotations

from .config import Settings


def analyzer_ready(settings: Settings) -> bool:
    provider = settings.ai_provider.lower()
    if provider in ("stub", "agent"):
        # The stub needs nothing. The agent needs `claude auth login`, which is
        # not something this process can see - a failure surfaces as a clear
        # AnalysisFailed on the first call instead.
        return True
    if provider == "claude":
        return bool(settings.anthropic_api_key)
    return False
