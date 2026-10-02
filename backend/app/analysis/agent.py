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

import io
import tempfile
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from PIL import Image
from pydantic import BaseModel, ValidationError

from ..query import BankQuery, Vocabulary
from .base import (
    AnalysisFailed,
    ConceptBrief,
    ConceptProposal,
    Filing,
    MistakeAnalysis,
    MistakeInput,
    Turn,
    VideoInput,
    VideoSummary,
)
from .claude import (
    DISCUSS_PROMPT,
    FILING_PROMPT,
    INTERPRET_PROMPT,
    PROPOSE_PROMPT,
    SUMMARISE_PROMPT,
    SYSTEM_PROMPT,
    VIDEO_PROMPT,
    _render,
    render_video,
)
from .scan import SCAN_PROMPT, ScanInput, ScannedQuestion

# Where a PDF or image lands before the agent reads it. The extension matters:
# the CLI decides how to open a file from its suffix.
_SUFFIX = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}

# Longest side of a picture handed to the agent. A phone photo is 4000px and
# 5MB; a question is still legible at this size and the read is seconds faster.
MAX_EDGE = 1800


def _shrink(data: bytes, suffix: str) -> tuple[bytes, str]:
    """Downscale a large photo and re-encode it as JPEG. Small ones pass through."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            if max(image.size) <= MAX_EDGE and len(data) <= 1_500_000:
                return data, suffix
            image.thumbnail((MAX_EDGE, MAX_EDGE))
            out = io.BytesIO()
            image.convert("RGB").save(out, format="JPEG", quality=85)
            return out.getvalue(), ".jpg"
    except OSError:
        return data, suffix


async def _run(
    *,
    prompt: str,
    system: str,
    model: str,
    schema: type[BaseModel] | None,
    cwd: str | None = None,
    allowed_tools: list[str] | None = None,
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
        # Only ever the Read tool, and only on a directory this process created.
        # Nothing to approve, and a permission prompt would hang a headless
        # subprocess.
        allowed_tools=allowed_tools or [],
        permission_mode="bypassPermissions" if allowed_tools else "default",
        max_turns=max_turns,
        cwd=cwd,
        # Reading a picture streams it back as base64 inside one JSON line. The
        # SDK's default 1MB line buffer rejects anything bigger than a small
        # screenshot with CLIJSONDecodeError.
        max_buffer_size=64 * 1024 * 1024,
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

    async def file_questions(self, concepts: list[ConceptBrief], digest: str) -> Filing:
        listed = "\n".join(
            f"- {c.title}" + (f": {c.body[:300]}" if c.body else "") for c in concepts
        )
        return await _run(
            prompt=f"The concepts:\n{listed}\n\nThe questions:\n{digest}",
            system=FILING_PROMPT,
            model=self._model,
            schema=Filing,
        )

    async def read_video(self, video: VideoInput) -> VideoSummary:
        return await _run(
            prompt=render_video(video),
            system=VIDEO_PROMPT,
            model=self._model,
            schema=VideoSummary,
            # A long lecture is a long prompt; the default turn budget is tight
            # for one that has to come back as 20 structured concepts.
            max_turns=12,
        )

    async def propose_concept(self, pattern: str, summary: str, digest: str) -> ConceptProposal:
        return await _run(
            prompt=(
                f"The habit: {pattern}\n{summary}\n\nThe questions filed under it:\n{digest}"
            ),
            system=PROPOSE_PROMPT,
            model=self._model,
            schema=ConceptProposal,
        )

    async def discuss(self, context: str, conversation: list[Turn]) -> str:
        # One prompt rather than a message list: this provider drives the agent
        # CLI, which takes a single turn, so the thread is written into the text.
        spoken = "\n\n".join(
            f"{'Student' if turn.role == 'student' else 'You'}: {turn.text}"
            for turn in conversation
        )
        return await _run(
            prompt=(
                f"The question, and the debrief already written for it:\n\n{context}"
                f"\n\nThe conversation so far:\n\n{spoken}"
            ),
            system=DISCUSS_PROMPT,
            model=self._model,
            schema=None,
        )


class AgentScanner:
    """Reads one question out of a picture or a PDF page.

    Pictures are not sent inline. They are written to a temporary directory and
    the agent is told to `Read` them, which is what the CLI's Read tool is for -
    it handles images and PDFs natively.
    """

    name = "agent"

    def __init__(self, model: str, mkdtemp: Callable[[], str] = tempfile.mkdtemp) -> None:
        self._model = model
        self._mkdtemp = mkdtemp

    async def read(self, scan: ScanInput) -> ScannedQuestion:
        suffix = _SUFFIX.get(scan.media_type)
        if suffix is None:
            raise AnalysisFailed(f"cannot hand a {scan.media_type} to the agent")

        data = scan.data
        if scan.kind == "image":
            data, suffix = _shrink(data, suffix)

        directory = self._mkdtemp()
        path = Path(directory) / f"question{suffix}"
        path.write_bytes(data)
        try:
            return await _run(
                prompt=(
                    f"The question is in the file at {path}. Read it with the Read "
                    "tool, then return the question, its answer choices, and the "
                    "correct answer - from the page if it states one, worked out "
                    "yourself if it does not."
                ),
                system=SCAN_PROMPT,
                model=self._model,
                schema=ScannedQuestion,
                cwd=directory,
                allowed_tools=["Read"],
                max_turns=12,
            )
        finally:
            path.unlink(missing_ok=True)
            Path(directory).rmdir()
