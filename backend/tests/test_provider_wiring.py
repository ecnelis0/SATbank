"""Pasting a key must be the only step. These pin the selection, not the network."""

from __future__ import annotations

import pytest

from app import config
from app.analysis import get_analyzer
from app.analysis.stub import StubAnalyzer


@pytest.fixture
def reconfigure(monkeypatch):
    def apply(**env: str) -> None:
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        config.get_settings.cache_clear()
        get_analyzer.cache_clear()

    yield apply
    config.get_settings.cache_clear()
    get_analyzer.cache_clear()


def test_the_default_is_the_offline_analyzer(reconfigure):
    reconfigure(AI_PROVIDER="stub")

    assert isinstance(get_analyzer(), StubAnalyzer)


def test_setting_the_provider_and_key_selects_the_real_one(reconfigure):
    """The whole "paste your key" story: two env vars, no code change."""
    reconfigure(AI_PROVIDER="claude", ANTHROPIC_API_KEY="sk-ant-test")
    analyzer = get_analyzer()

    assert type(analyzer).__name__ == "ClaudeAnalyzer"
    assert analyzer.name == "claude"
    # And it satisfies the whole contract, not just the part the log form uses.
    assert all(hasattr(analyzer, m) for m in ("analyze", "interpret", "summarise"))


def test_the_model_is_configurable_without_touching_code(reconfigure):
    reconfigure(
        AI_PROVIDER="claude",
        ANTHROPIC_API_KEY="sk-ant-test",
        ANTHROPIC_MODEL="claude-sonnet-5",
    )

    assert get_analyzer()._model == "claude-sonnet-5"


def test_an_unknown_provider_fails_loudly_rather_than_falling_back(reconfigure):
    reconfigure(AI_PROVIDER="gpt")

    with pytest.raises(ValueError, match="Unknown AI_PROVIDER"):
        get_analyzer()


async def test_health_says_the_offline_analyzer_is_ready(client):
    body = (await client.get("/health")).json()

    assert body["analyzer"] == "stub"
    assert body["analyzer_ready"] is True


async def test_health_reports_a_provider_selected_without_a_key(client, reconfigure):
    """ "The AI is off" and "the AI is misconfigured" must not look the same."""
    reconfigure(AI_PROVIDER="claude", ANTHROPIC_API_KEY="")

    body = (await client.get("/health")).json()

    assert body["analyzer"] == "claude"
    assert body["analyzer_ready"] is False


async def test_health_reports_ready_once_the_key_is_pasted(client, reconfigure):
    reconfigure(AI_PROVIDER="claude", ANTHROPIC_API_KEY="sk-ant-test")

    body = (await client.get("/health")).json()

    assert body["analyzer_ready"] is True
    assert body["model"] == "claude-opus-5"
