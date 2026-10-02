"""Anthropic-backed analyzer.

Uses structured outputs (`messages.parse`) so the response is a validated
`MistakeAnalysis` rather than prose we would have to scrape.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import anthropic
import httpx2

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

if TYPE_CHECKING:
    from .scan import ScanInput, ScannedQuestion

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
"Reading", "verbal" and "English" all mean the reading_writing section.

You are given the topics and concepts this bank actually contains. When the student \
names something, match it to those - copy the exact strings. Do not invent a topic or a \
concept title; a filter on a string that is not in the bank silently returns nothing, \
which reads to the student as "you have no such questions".

If the student is asking about the bank as a whole ("what am I worst at", "what should I \
review first") rather than for a subset, return an empty filter and let them see \
everything - the counts are computed separately and you will get them.

"What have I consistently been getting wrong in the past month" is a date range and \
nothing else: set logged_after and leave every other field empty. Narrowing it to one \
topic would hide the very pattern they are asking you to find.\
"""

FILING_PROMPT = """\
A student keeps a set of revision concepts, and a bank of questions they got \
wrong. You are deciding which of those questions each concept actually \
explains.

File a question under a concept only when the concept is the thing that would \
have helped - the rule they needed, or the step they skipped. Sharing a topic \
is not enough: a concept about semicolons does not collect every punctuation \
question, and "quadratics" is not a reason to file a quadratics question under \
a concept about checking your working.

Returning nothing is a good answer. A concept that has collected every \
loosely-related question tells the student nothing, and they will stop trusting \
all of them. Be strict; they can always tag more by hand.

Use the ids exactly as given, and only concepts from the list you were \
handed."""


VIDEO_PROMPT = """\
You are turning a video a student is studying from into concepts they can \
revise, and later attach their own missed questions to.

Break it into the *ideas it teaches*, not into the sections it happens to have. \
A video that spends eleven minutes on one comma rule is one concept, not four; \
a video that races through eight rules is eight. Skip the introduction, the \
sign-off and anything about the channel - nobody revises from "make sure to \
subscribe".

Write each concept so it stands on its own without the video open. Title it the \
way a student would look it up, and put the rule and how to apply it in the \
body, keeping the examples that earn their place.

The transcript is marked with [123s] stamps. Give each concept the stamp where \
its explanation starts, so the student can jump straight there.

If you are given concepts the student already has and the video teaches one of \
them, reuse that exact title - a second video on the same rule should deepen the \
note they have, not sit beside it as a near-copy.

If the student gave directions, they outrank everything above except honesty: \
follow them. If the transcript is not teaching material at all, say so in the \
summary and return no concepts rather than inventing some."""


PROPOSE_PROMPT = """\
A student's mistake bank has collected several questions under one recurring \
habit. You are deciding what single idea sits underneath them, so they can \
write it down once instead of re-learning it a question at a time.

You are given the habit, and the questions filed under it with their debriefs.

Name the *rule or idea*, not the habit - the habit already has a name. "Read \
the question stem before the answers" is a rule; "rushes" is a habit. If the \
questions genuinely share a step - and they usually do, because that is why \
they ended up together - the first step they all skipped is normally the \
concept.

Say what went wrong across all of them as one recurring move in the second \
person, not as a list of the individual misses. The student has already read \
each debrief; what they have not seen is the thing those debriefs have in \
common.

Write the body as their own revision note: the rule, then how to apply it next \
time. Short. If the questions do not actually share one idea, say so in \
`why_a_concept` rather than inventing a link - a concept that is really three \
concepts is worse than none."""


DISCUSS_PROMPT = """\
You are a patient SAT tutor talking to a student about one question they got \
wrong. You are given the question, what they answered, the correct answer, \
anything they wrote about what happened, and the debrief already written for \
them. The conversation so far follows.

Answer the question they actually asked. Three kinds come up and they want \
different things:

* "What does this mean?" - a word in the debrief, a term, a piece of notation. \
  Define it in plain language and point at where it shows up in *their* \
  question. Do not re-explain the whole thing.
* "Why is my answer wrong?" or "where did I go wrong?" - walk the step they \
  missed, using their own answer as the starting point, not the correct one.
* "How do I do this next time?" - give the method, then apply it to this \
  question so it is concrete.

Stay on this question. If they ask something the question cannot answer - about \
the rest of their bank, or about another topic entirely - say so in a sentence \
and answer what you can.

Be brief. Two or three short paragraphs at most, no headings, no bullet lists \
unless you are genuinely enumerating steps. You are talking, not writing a \
worksheet. Never tell them the debrief is wrong without saying what is right."""


SUMMARISE_PROMPT = """\
You are answering a student's question about their own SAT mistake bank.

You are given the rows that actually matched their question. Use only those rows - do \
not estimate, extrapolate, or mention questions that are not listed. If nothing matched, \
say so plainly and suggest a looser question.

When they ask what they *keep* getting wrong - "consistently", "always", "again and \
again", "over the past month" - two things count, and you are given both:

* several *different* questions missed in the same topic, concept or for the same \
  reason. Four different inverse trig questions, each wrong once, is a weakness in \
  inverse trig even though no single one has come back.
* the same question still wrong when it came round again.

Lead with whichever is stronger, name the topic, concept or reason, and give the number. \
A single question wrong once is not a pattern; do not invent one.

Two or three sentences. Lead with the count, then the pattern worth noticing - the slot \
or topic that keeps recurring, not a restatement of the list they can already see.\
"""


def render_video(video: VideoInput) -> str:
    """Everything the summariser is told about a video, in one prompt."""
    parts: list[str] = []
    if video.title:
        parts.append(f"Video: {video.title}")
    if video.author:
        parts.append(f"Channel: {video.author}")
    if video.subject:
        parts.append(f"The student files this under: {video.subject}")
    if video.directions:
        # Last of the framing and clearly labelled, so it is the instruction the
        # model is still holding when it reaches the transcript.
        parts.append(f"\nThe student's directions for this video: {video.directions}")
    if not video.has_timestamps:
        parts.append(
            "\nThis transcript was pasted by the student and has no timestamps, so "
            "leave start_seconds null."
        )
    if video.truncated:
        parts.append(
            "\nThis transcript is cut off before the end of the video. Say so in the "
            "summary and do not guess at what followed."
        )
    if video.known_concepts:
        listed = "\n".join(f"- {title}" for title in video.known_concepts)
        parts.append(
            "\nConcepts this student already has. If the video teaches one of these, "
            "reuse its exact title so the note deepens instead of being duplicated:\n"
            + listed
        )
    parts.append(f"\nTranscript:\n{video.transcript}")
    return "\n".join(parts)


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
    if mistake.known_concepts:
        listed = "\n".join(
            f"- {c.title}" + (f": {c.body[:200]}" if c.body else "")
            for c in mistake.known_concepts
        )
        parts.append(
            "\nThe student's own revision concepts. If this question is genuinely an "
            "instance of one, name it in `concepts` so it is filed where they would "
            "look for it. Leave it empty rather than stretching - a concept that has "
            "collected every loosely-related question is useless:\n" + listed
        )
    if mistake.known_patterns:
        listed = "\n".join(f"- {title}" for title in mistake.known_patterns)
        parts.append(
            "\nPatterns already named in this student's bank. Reuse one word for word "
            "wherever it fits, so their questions collect under it instead of under a "
            "near-copy:\n" + listed
        )
    return "\n".join(parts)


class ClaudeAnalyzer:
    name = "claude"

    def __init__(
        self,
        api_key: str | None,
        model: str,
        http_client: httpx2.AsyncClient | None = None,
        base_url: str | None = None,
    ) -> None:
        # `http_client` and `base_url` exist for the test that drives this class
        # against a stand-in Anthropic endpoint. In the app both are None and the
        # SDK talks to Anthropic, reading ANTHROPIC_BASE_URL from the environment
        # if it is set.
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            **({"http_client": http_client} if http_client else {}),
            **({"base_url": base_url} if base_url else {}),
        )
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

    async def interpret(self, question: str, today: date, vocabulary: Vocabulary) -> BankQuery:
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
                            f"Today is {today.isoformat()}.\n\n"
                            f"{vocabulary.render()}\n\n"
                            f"The student asked: {question}"
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

    async def file_questions(self, concepts: list[ConceptBrief], digest: str) -> Filing:
        listed = "\n".join(
            f"- {c.title}" + (f": {c.body[:300]}" if c.body else "") for c in concepts
        )
        try:
            response = await self._client.messages.parse(
                model=self._model,
                max_tokens=8000,
                system=FILING_PROMPT,
                thinking={"type": "adaptive"},
                messages=[
                    {
                        "role": "user",
                        "content": f"The concepts:\n{listed}\n\nThe questions:\n{digest}",
                    }
                ],
                output_format=Filing,
            )
        except anthropic.APIError as exc:
            raise AnalysisFailed(f"{type(exc).__name__}: {exc}") from exc

        if response.stop_reason == "refusal":
            raise AnalysisFailed("the model declined to file those questions")
        parsed = response.parsed_output
        if parsed is None:
            raise AnalysisFailed("model returned no structured output")
        return parsed

    async def read_video(self, video: VideoInput) -> VideoSummary:
        try:
            response = await self._client.messages.parse(
                model=self._model,
                max_tokens=16000,
                system=VIDEO_PROMPT,
                thinking={"type": "adaptive"},
                messages=[{"role": "user", "content": render_video(video)}],
                output_format=VideoSummary,
            )
        except anthropic.APIError as exc:
            raise AnalysisFailed(f"{type(exc).__name__}: {exc}") from exc

        if response.stop_reason == "refusal":
            raise AnalysisFailed("the model declined to read that video")
        parsed = response.parsed_output
        if parsed is None:
            raise AnalysisFailed("model returned no structured output")
        return parsed

    async def propose_concept(self, pattern: str, summary: str, digest: str) -> ConceptProposal:
        try:
            response = await self._client.messages.parse(
                model=self._model,
                max_tokens=8000,
                system=PROPOSE_PROMPT,
                thinking={"type": "adaptive"},
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"The habit: {pattern}\n{summary}\n\n"
                            f"The questions filed under it:\n{digest}"
                        ),
                    }
                ],
                output_format=ConceptProposal,
            )
        except anthropic.APIError as exc:
            raise AnalysisFailed(f"{type(exc).__name__}: {exc}") from exc

        if response.stop_reason == "refusal":
            raise AnalysisFailed("the model declined to answer")
        parsed = response.parsed_output
        if parsed is None:
            raise AnalysisFailed("model returned no structured output")
        return parsed

    async def discuss(self, context: str, conversation: list[Turn]) -> str:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=DISCUSS_PROMPT,
                messages=_Discuss.messages(context, conversation),
            )
        except anthropic.APIError as exc:
            raise AnalysisFailed(f"{type(exc).__name__}: {exc}") from exc

        if response.stop_reason == "refusal":
            raise AnalysisFailed("the model declined to answer")
        return "".join(block.text for block in response.content if block.type == "text")


class _Discuss:
    """Mixin: the conversation turned into messages, for the API provider."""

    @staticmethod
    def messages(context: str, conversation: list[Turn]) -> list[dict[str, str]]:
        head = f"The question, and the debrief already written for it:\n\n{context}"
        messages = [{"role": "user", "content": head}]
        for turn in conversation:
            messages.append(
                {
                    "role": "user" if turn.role == "student" else "assistant",
                    "content": turn.text,
                }
            )
        return messages


class ClaudeScanner:
    """Reads one question out of a picture, over the API. Mirrors `AgentScanner`."""

    name = "claude"

    def __init__(
        self,
        api_key: str | None,
        model: str,
        http_client: httpx2.AsyncClient | None = None,
        base_url: str | None = None,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            **({"http_client": http_client} if http_client else {}),
            **({"base_url": base_url} if base_url else {}),
        )
        self._model = model

    async def read(self, scan: ScanInput) -> ScannedQuestion:
        import base64

        from .scan import SCAN_PROMPT
        from .scan import ScannedQuestion as Schema

        blocks: list[dict] = [
            {
                "type": "image" if scan.kind == "image" else "document",
                "source": {
                    "type": "base64",
                    "media_type": scan.media_type,
                    "data": base64.standard_b64encode(scan.data).decode("ascii"),
                },
            },
            {"type": "text", "text": "Read the question in this picture and return its fields."},
        ]

        try:
            response = await self._client.messages.parse(
                model=self._model,
                max_tokens=8000,
                system=SCAN_PROMPT,
                thinking={"type": "adaptive"},
                messages=[{"role": "user", "content": blocks}],
                output_format=Schema,
            )
        except anthropic.APIError as exc:
            raise AnalysisFailed(f"{type(exc).__name__}: {exc}") from exc

        if response.stop_reason == "refusal":
            raise AnalysisFailed("the model declined to read that picture")
        parsed = response.parsed_output
        if parsed is None:
            raise AnalysisFailed("model returned no structured output")
        return parsed
