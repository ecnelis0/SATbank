"""Claude Agent SDK provider: runs on your Claude plan login, no API key.

`AI_PROVIDER=agent`. The Agent SDK drives the Claude Code CLI as a subprocess,
and the CLI uses whatever `claude auth login` stored - so a claude.ai
subscription pays for the calls and no key goes in `.env`. Nothing else
changes: the same prompts and the same structured output schemas as the API
adapter in `claude.py`, so the two are interchangeable and a test written
against one covers the request shape of the other.

The one thing it cannot do is run anywhere but this machine. The login lives in
a keychain, so a container or a Fly machine has to use `AI_PROVIDER=claude` and
a real key.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ValidationError

from ..query import BankQuery, Vocabulary
from .base import AnalysisFailed, MistakeAnalysis, MistakeInput
from .claude import INTERPRET_PROMPT, SUMMARISE_PROMPT, SYSTEM_PROMPT, _render


async def _run(
    *,
    prompt: str,
    system: str,
    model: str,
    schema: type[BaseModel] | None,
    # Structured output arrives through an internal tool turn, so even a no-tool
    # call needs more than one: max_turns=1 fails intermittently with "Reached
    # maximum number of turns (1)".
    max_turns: int = 8,
) -> Any:
    """One agent turn. Returns the validated structured output, or the text."""
    try:
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ClaudeSDKError,
            ResultMessage,
            TextBlock,
            query,
        )
    except ImportError as exc:
        raise AnalysisFailed(
            "claude-agent-sdk is not installed: run `uv sync` in backend/"
        ) from exc

    options = ClaudeAgentOptions(
        model=model,
        system_prompt=system,
        # No tools at all: this provider only ever reasons about text it was
        # handed, and a permission prompt would hang a headless subprocess.
        allowed_tools=[],
        max_turns=max_turns,
        **(
            {"output_format": {"type": "json_schema", "schema": schema.model_json_schema()}}
            if schema
            else {}
        ),
    )

    text: list[str] = []
    result: ResultMessage | None = None
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                text.extend(b.text for b in message.content if isinstance(b, TextBlock))
            elif isinstance(message, ResultMessage):
                result = message
    except ClaudeSDKError as exc:  # CLI missing, not logged in, process died
        raise AnalysisFailed(f"{type(exc).__name__}: {exc}") from exc

    if result is None:
        raise AnalysisFailed("the agent returned no result")
    if result.is_error:
        detail = "; ".join(result.errors or []) or result.result or result.subtype
        raise AnalysisFailed(f"agent error: {detail}")
    if result.stop_reason == "refusal":
        raise AnalysisFailed("model declined to answer")

    if schema is None:
        return "".join(text).strip() or (result.result or "")
    if result.structured_output is None:
        raise AnalysisFailed("model returned no structured output")
    try:
        return schema.model_validate(result.structured_output)
    except ValidationError as exc:
        raise AnalysisFailed(f"structured output did not validate: {exc}") from exc


class AgentAnalyzer:
    name = "agent"

    def __init__(self, model: str) -> None:
        self._model = model

    async def analyze(self, mistake: MistakeInput) -> MistakeAnalysis:
        return await _run(
            prompt=_render(mistake),
            system=SYSTEM_PROMPT,
            model=self._model,
            schema=MistakeAnalysis,
        )

    async def interpret(self, question: str, today: date, vocabulary: Vocabulary) -> BankQuery:
        prompt = (
            f"Today is {today.isoformat()}.\n\n{vocabulary.render()}\n\n"
            f"The student asked: {question}"
        )
        try:
            return await _run(
                prompt=prompt, system=INTERPRET_PROMPT, model=self._model, schema=BankQuery
            )
        except AnalysisFailed as exc:
            raise AnalysisFailed(f"the model would not read that as a search ({exc})") from exc

    async def summarise(self, question: str, digest: str) -> str:
        return await _run(
            prompt=f"The student asked: {question}\n\nMatching rows:\n{digest}",
            system=SUMMARISE_PROMPT,
            model=self._model,
            schema=None,
        )
