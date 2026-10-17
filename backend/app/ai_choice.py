"""Which AI is in charge right now - switchable from the app or the terminal.

`AI_PROVIDER` in `.env` is where the app starts. The student can change it while
it runs (the switch in the nav, or `./ai.sh` from the repo root), and that choice
is written to a small file and read on every call. Read every time rather than
cached, so a switch made from the terminal lands on the very next request
without a restart - and a restart does not quietly undo it.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from .config import Settings, get_settings

PROVIDERS = ("agent", "openai", "claude", "stub")

# What the student sees. "agent" is the internal name for the Claude Agent SDK;
# nobody choosing between two AIs should have to know that.
LABELS: dict[str, str] = {
    "agent": "Claude",
    "openai": "OpenAI",
    "claude": "Claude API",
    "stub": "AI off",
}

DESCRIPTIONS: dict[str, str] = {
    "agent": "Runs on your Claude plan through Claude Code on this Mac. No API key.",
    "openai": "Uses the OpenAI API key in .env. Billed to your OpenAI account.",
    "claude": "Uses an Anthropic API key in .env. Billed to that account.",
    "stub": "No model. Questions are logged and scheduled, debriefs are placeholders.",
}


class ProviderOption(BaseModel):
    id: str
    label: str
    description: str
    ready: bool


class AiChoice(BaseModel):
    provider: str
    label: str
    ready: bool
    # Where the choice came from: "switch" once the student has picked one,
    # ".env" until then. Lets the UI explain why it says what it says.
    source: str
    options: list[ProviderOption]


def _path(settings: Settings) -> Path | None:
    # getattr: a settings object built without the field (as some tests build
    # them) simply has no switch, and .env decides.
    location = getattr(settings, "ai_choice_file", None)
    return Path(location) if location else None


def chosen_provider(settings: Settings | None = None) -> str | None:
    """The student's switched choice, or None if they have not made one."""
    settings = settings or get_settings()
    path = _path(settings)
    if path is None:
        return None
    try:
        value = path.read_text().strip().lower()
    except (FileNotFoundError, OSError):
        return None
    # A hand-edited file with a typo falls back to .env rather than taking the AI
    # down: the choice is a preference, and a bad one should not cost a debrief.
    return value if value in PROVIDERS else None


def current_provider(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return chosen_provider(settings) or settings.ai_provider.lower()


def set_provider(provider: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    provider = provider.strip().lower()
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider {provider!r}; expected one of {', '.join(PROVIDERS)}")
    path = _path(settings)
    if path is None:
        raise ValueError("No AI_CHOICE_FILE is configured to keep the choice in")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(provider + "\n")
    return provider


def describe(settings: Settings | None = None) -> AiChoice:
    from .readiness import provider_ready

    settings = settings or get_settings()
    provider = current_provider(settings)
    return AiChoice(
        provider=provider,
        label=LABELS.get(provider, provider),
        ready=provider_ready(provider, settings),
        source="switch" if chosen_provider(settings) else ".env",
        options=[
            ProviderOption(
                id=option,
                label=LABELS[option],
                description=DESCRIPTIONS[option],
                ready=provider_ready(option, settings),
            )
            for option in PROVIDERS
        ],
    )
