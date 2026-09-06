"""Anthropic-backed analyzer.

Uses structured outputs (`messages.parse`) so the response is a validated
`MistakeAnalysis` rather than prose we would have to scrape.
"""

from __future__ import annotations

import anthropic

from .base import AnalysisFailed, MistakeAnalysis, MistakeInput

SYSTEM_PROMPT = """\
You are an SAT tutor reviewing a question a student got wrong, so it can be filed in \
their mistake bank.

Diagnose the student, not the question. The interesting thing is what their specific \
wrong answer reveals about how they were thinking - a sign error, a misread stem, a \
missing rule, a trap they walked into. Address them as "you". Be concrete and short; \
this text is read again a month later, on a phone, under time pressure.

Pick the single error_type that best explains this particular miss. If the student left \
a note about what happened, weight it heavily - they were there and you were not.\
"""


def _render(mistake: MistakeInput) -> str:
    parts = [f"Section: {mistake.section}"]
    if mistake.source:
        parts.append(f"Source: {mistake.source}")
    parts.append(f"\nQuestion:\n{mistake.question_text}")
    if mistake.choices:
        rendered = "\n".join(f"{chr(65 + i)}. {choice}" for i, choice in enumerate(mistake.choices))
        parts.append(f"\nChoices:\n{rendered}")
    parts.append(f"\nThe student answered: {mistake.your_answer}")
    parts.append(f"The correct answer is: {mistake.correct_answer}")
    if mistake.student_note:
        parts.append(f"\nThe student's own note: {mistake.student_note}")
    return "\n".join(parts)


class ClaudeAnalyzer:
    name = "claude"

    def __init__(self, api_key: str | None, model: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def analyze(self, mistake: MistakeInput) -> MistakeAnalysis:
        try:
            response = await self._client.messages.parse(
                model=self._model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                thinking={"type": "adaptive"},
                messages=[{"role": "user", "content": _render(mistake)}],
                output_format=MistakeAnalysis,
            )
        except anthropic.APIError as exc:  # network, rate limit, bad key, 5xx
            raise AnalysisFailed(f"{type(exc).__name__}: {exc}") from exc

        if response.stop_reason == "refusal":
            detail = getattr(response.stop_details, "explanation", None) or "no explanation"
            raise AnalysisFailed(f"model declined to answer ({detail})")

        parsed = response.parsed_output
        if parsed is None:
            raise AnalysisFailed("model returned no structured output")
        return parsed
