"""Switching which AI the app uses, while it runs."""

from __future__ import annotations

from app import config
from app.ai_choice import current_provider, set_provider
from app.analysis import get_analyzer
from app.analysis.scan import get_scanner
from tests.conftest import MATH_MISTAKE


async def test_with_no_switch_the_env_decides(client):
    body = (await client.get("/ai")).json()
    assert body["provider"] == "stub"
    assert body["source"] == ".env"
    assert {o["id"] for o in body["options"]} == {"agent", "openai", "claude", "stub"}


async def test_switching_takes_effect_on_the_next_call_without_a_restart(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    config.get_settings.cache_clear()

    switched = await client.put("/ai", json={"provider": "openai"})
    assert switched.status_code == 200
    assert switched.json()["provider"] == "openai"
    assert switched.json()["source"] == "switch"

    # The same process, no cache cleared by hand: the next lookup is the new one.
    assert get_analyzer().name == "openai"
    assert get_scanner().name == "openai"
    assert (await client.get("/health")).json()["analyzer"] == "openai"

    await client.put("/ai", json={"provider": "stub"})
    assert get_analyzer().name == "stub"


async def test_the_switch_beats_the_env(client, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    config.get_settings.cache_clear()
    set_provider("agent")
    assert current_provider() == "agent"
    assert get_analyzer().name == "agent"


async def test_an_unknown_provider_is_refused_and_changes_nothing(client):
    response = await client.put("/ai", json={"provider": "gemini"})
    assert response.status_code == 422
    assert (await client.get("/ai")).json()["provider"] == "stub"


async def test_a_garbled_choice_file_falls_back_to_the_env(client):
    """A typo in a hand-edited file must not take the AI down."""
    path = config.get_settings().ai_choice_file
    with open(path, "w") as handle:
        handle.write("opeani\n")
    assert current_provider() == "stub"
    response = await client.post("/mistakes", json=MATH_MISTAKE)
    assert response.status_code == 201


async def test_readiness_follows_the_switch(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config.get_settings.cache_clear()
    body = (await client.put("/ai", json={"provider": "openai"})).json()
    # OpenAI with no key is selected but not usable - the UI has to be able to say so.
    assert body["ready"] is False
    openai = next(o for o in body["options"] if o["id"] == "openai")
    assert openai["ready"] is False


def test_the_terminal_command_understands_what_the_student_types(app_env, capsys):
    from scripts.ai import main

    assert main(["claude"]) == 0
    assert current_provider() == "agent"
    assert main(["openai"]) == 0
    assert current_provider() == "openai"
    assert main(["off"]) == 0
    assert current_provider() == "stub"
    assert main(["bard"]) == 2
    assert current_provider() == "stub"
    assert "AI now:" in capsys.readouterr().out
