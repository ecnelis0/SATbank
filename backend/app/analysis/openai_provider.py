"""The OpenAI provider: the same contract, the same prompts, a different model.

Every prompt here is imported from `claude.py` rather than rewritten. They are
the product - what the app asks for and what it refuses to accept - and keeping
two copies in step by hand is how two providers quietly start behaving
differently.

The one real difference is structured output. OpenAI's strict mode accepts a
narrow subset of JSON Schema, and the schemas Pydantic generates from our models
are outside it: `maxLength`, `maxItems` and `default` all appear and all are
rejected. `strict_schema` below trims them.
"""

from __future__ import annotations

import base64
from datetime import date
from typing import Any, TypeVar

import openai
from pydantic import BaseModel

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

Model = TypeVar("Model", bound=BaseModel)

# Keywords OpenAI's strict structured output does not accept. Left in, the API
# rejects the whole request with "Invalid schema" and names one of them.
UNSUPPORTED = (
    "maxLength",
    "minLength",
    "pattern",
    "format",
    "maxItems",
    "minItems",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "default",
)


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """A JSON Schema OpenAI will accept, from one of our Pydantic models.

    Strict mode also requires every property to be listed as required and every
    object to forbid extra properties. A field our model gives a default is still
    required here; the model always emits it, and Pydantic applies the default if
    it somehow does not.
    """

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node

        cleaned = {key: walk(value) for key, value in node.items() if key not in UNSUPPORTED}
        if cleaned.get("type") == "object" or "properties" in cleaned:
            properties = cleaned.get("properties", {})
            cleaned["additionalProperties"] = False
            cleaned["required"] = list(properties)
        return cleaned

    return walk(model.model_json_schema())


class OpenAIAnalyzer:
    name = "openai"

    def __init__(self, api_key: str | None, model: str, client: Any | None = None) -> None:
        self._client = client or openai.AsyncOpenAI(api_key=api_key)
        self._model = model

    async def _structured(self, system: str, prompt: str, schema: type[Model]) -> Model:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema.__name__,
                        "schema": strict_schema(schema),
                        "strict": True,
                    },
                },
            )
        except openai.OpenAIError as exc:  # bad key, rate limit, network, 5xx
            raise AnalysisFailed(f"{type(exc).__name__}: {exc}") from exc

        choice = response.choices[0]
        if getattr(choice.message, "refusal", None):
            raise AnalysisFailed(f"the model declined to answer ({choice.message.refusal})")
        content = choice.message.content
        if not content:
            raise AnalysisFailed("model returned no structured output")
        try:
            return schema.model_validate_json(content)
        except ValueError as exc:
            raise AnalysisFailed(f"model returned output we could not read: {exc}") from exc

    async def _text(self, system: str, messages: list[dict[str, str]]) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "system", "content": system}, *messages],
            )
        except openai.OpenAIError as exc:
            raise AnalysisFailed(f"{type(exc).__name__}: {exc}") from exc
        return response.choices[0].message.content or ""

    # --- the contract ---------------------------------------------------------

    async def analyze(self, mistake: MistakeInput) -> MistakeAnalysis:
        return await self._structured(SYSTEM_PROMPT, _render(mistake), MistakeAnalysis)

    async def interpret(self, question: str, today: date, vocabulary: Vocabulary) -> BankQuery:
        prompt = (
            f"Today is {today.isoformat()}.\n\n{vocabulary.render()}\n\n"
            f"The student asked: {question}"
        )
        try:
            return await self._structured(INTERPRET_PROMPT, prompt, BankQuery)
        except AnalysisFailed as exc:
            raise AnalysisFailed(f"the model would not read that as a search ({exc})") from exc

    async def summarise(self, question: str, digest: str) -> str:
        asked = f"The student asked: {question}\n\nMatching rows:\n{digest}"
        return await self._text(SUMMARISE_PROMPT, [{"role": "user", "content": asked}])

    async def discuss(self, context: str, conversation: list[Turn]) -> str:
        messages: list[dict[str, str]] = [
            {
                "role": "user",
                "content": f"The question, and the debrief already written for it:\n\n{context}",
            }
        ]
        for turn in conversation:
            messages.append(
                {
                    "role": "user" if turn.role == "student" else "assistant",
                    "content": turn.text,
                }
            )
        return await self._text(DISCUSS_PROMPT, messages)

    async def propose_concept(self, pattern: str, summary: str, digest: str) -> ConceptProposal:
        return await self._structured(
            PROPOSE_PROMPT,
            f"The habit: {pattern}\n{summary}\n\nThe questions filed under it:\n{digest}",
            ConceptProposal,
        )

    async def file_questions(self, concepts: list[ConceptBrief], digest: str) -> Filing:
        listed = "\n".join(
            f"- {c.title}" + (f": {c.body[:300]}" if c.body else "") for c in concepts
        )
        return await self._structured(
            FILING_PROMPT, f"The concepts:\n{listed}\n\nThe questions:\n{digest}", Filing
        )

    async def read_video(self, video: VideoInput) -> VideoSummary:
        return await self._structured(VIDEO_PROMPT, render_video(video), VideoSummary)


class OpenAIScanner:
    """Reads one question out of a picture. Mirrors `ClaudeScanner`."""

    name = "openai"

    def __init__(self, api_key: str | None, model: str, client: Any | None = None) -> None:
        self._client = client or openai.AsyncOpenAI(api_key=api_key)
        self._model = model

    async def read(self, scan: ScanInput) -> ScannedQuestion:
        if scan.kind == "pdf":
            # Chat completions take images, not PDFs. Saying so beats a decode
            # error from somewhere deep in the SDK.
            raise AnalysisFailed(
                "This reader takes pictures rather than PDFs. Screenshot the page and "
                "send that instead."
            )

        encoded = base64.b64encode(scan.data).decode()
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SCAN_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{scan.media_type};base64,{encoded}"
                                },
                            }
                        ],
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "ScannedQuestion",
                        "schema": strict_schema(ScannedQuestion),
                        "strict": True,
                    },
                },
            )
        except openai.OpenAIError as exc:
            raise AnalysisFailed(f"{type(exc).__name__}: {exc}") from exc

        content = response.choices[0].message.content
        if not content:
            raise AnalysisFailed("model returned no structured output")
        try:
            return ScannedQuestion.model_validate_json(content)
        except ValueError as exc:
            raise AnalysisFailed(f"model returned output we could not read: {exc}") from exc
