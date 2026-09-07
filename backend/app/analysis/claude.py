"""Anthropic-backed analyzer.

Uses structured outputs (`messages.parse`) so the response is a validated
`MistakeAnalysis` rather than prose we would have to scrape.
"""

from __future__ import annotations

from datetime import date

import anthropic

from ..query import BankQuery
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


INTERPRET_PROMPT = """\
You turn a student's question about their SAT mistake bank into a database filter.

Return only the filter. You are not answering the question - something else runs the \
filter and reports the rows. Leave a field empty when the student did not constrain it; \
an over-tight filter silently hides their own work from them.

Resolve every relative date against today's date, given below, and write absolute dates. \
"Reading", "verbal" and "English" all mean the reading_writing section.\
"""

SUMMARISE_PROMPT = """\
You are answering a student's question about their own SAT mistake bank.

You are given the rows that actually matched their question. Use only those rows - do \
not estimate, extrapolate, or mention questions that are not listed. If nothing matched, \
say so plainly and suggest a looser question.

Two or three sentences. Lead with the count, then the pattern worth noticing - the slot \
or topic that keeps recurring, not a restatement of the list they can already see.\
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

    async def interpret(self, question: str, today: date) -> BankQuery:
        try:
            response = await self._client.messages.parse(
                model=self._model,
                max_tokens=4096,
                system=INTERPRET_PROMPT,
                thinking={"type": "adaptive"},
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Today is {today.isoformat()}.\n\nThe student asked: {question}"
                        ),
                    }
                ],
                output_format=BankQuery,
            )
        except anthropic.APIError as exc:
            raise AnalysisFailed(f"{type(exc).__name__}: {exc}") from exc

        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise AnalysisFailed("the model would not read that as a search")
        return response.parsed_output

    async def summarise(self, question: str, digest: str) -> str:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=SUMMARISE_PROMPT,
                thinking={"type": "adaptive"},
                messages=[
                    {
                        "role": "user",
                        "content": f"The student asked: {question}\n\nMatching rows:\n{digest}",
                    }
                ],
            )
        except anthropic.APIError as exc:
            raise AnalysisFailed(f"{type(exc).__name__}: {exc}") from exc

        if response.stop_reason == "refusal":
            raise AnalysisFailed("the model declined to answer")
        return "".join(block.text for block in response.content if block.type == "text")
