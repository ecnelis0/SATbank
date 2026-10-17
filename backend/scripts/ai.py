"""Switch which AI the bank uses, from the terminal.

    ./ai.sh              which one is on now
    ./ai.sh claude       Claude, on your Claude plan (Claude Agent SDK, no key)
    ./ai.sh openai       OpenAI, on the key in .env
    ./ai.sh claude-api   Claude, on an Anthropic API key in .env
    ./ai.sh off          no AI

Works whether or not the server is running: the choice is a file the API reads
on every call, so a running server picks it up on its next request.
"""

from __future__ import annotations

import sys

from app.ai_choice import describe, set_provider

# What the student types, mapped to the provider's internal name. "claude" is
# the Agent SDK because that is the Claude this machine can actually use without
# a key; the API-key route is the one that needs spelling out.
ALIASES = {
    "claude": "agent",
    "agent": "agent",
    "sdk": "agent",
    "openai": "openai",
    "gpt": "openai",
    "claude-api": "claude",
    "anthropic": "claude",
    "off": "stub",
    "stub": "stub",
}


def show() -> None:
    choice = describe()
    print(f"AI now: {choice.label} ({choice.provider}), set from {choice.source}")
    if not choice.ready:
        print("  Not ready: its API key is missing from .env.")
    print()
    for option in choice.options:
        mark = "*" if option.id == choice.provider else " "
        print(f" {mark} {option.label:<11} {option.description}")


def main(argv: list[str]) -> int:
    if not argv:
        show()
        return 0
    wanted = ALIASES.get(argv[0].strip().lower())
    if wanted is None:
        print(f"Unknown choice {argv[0]!r}. Use one of: claude, openai, claude-api, off.")
        return 2
    set_provider(wanted)
    show()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
