"""Offline analyzer.

Runs with no API key so the whole loop - log, analyse, bank, review - works before
a provider is picked, and so tests never touch the network. Its text is obviously
canned; it is not meant to teach anyone anything.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from ..models import Difficulty, ErrorType, Section, Urgency
from ..query import BankQuery, Vocabulary
from .base import (
    ConceptBrief,
    ConceptMatch,
    ConceptProposal,
    Filing,
    MistakeAnalysis,
    MistakeInput,
    PatternTag,
    Turn,
    VideoConcept,
    VideoInput,
    VideoSummary,
)

_MATH_HINTS = {
    "equation": "linear equations",
    "triangle": "geometry",
    "circle": "circles",
    "probability": "probability",
    "percent": "percentages",
    "function": "functions",
}
_VERBAL_HINTS = {
    "underlined": "sentence structure",
    "evidence": "command of evidence",
    "author": "author's purpose",
    "word": "words in context",
    "comma": "punctuation",
}


def _guess_topic(text: str, section: str) -> str:
    hints = _MATH_HINTS if section == "math" else _VERBAL_HINTS
    lowered = text.lower()
    for needle, topic in hints.items():
        if needle in lowered:
            return topic
    return "math fundamentals" if section == "math" else "reading comprehension"


def _guess_error_type(mistake: MistakeInput) -> ErrorType:
    if mistake.section == "math":
        both_numeric = all(_looks_numeric(v) for v in (mistake.your_answer, mistake.correct_answer))
        return ErrorType.careless_arithmetic if both_numeric else ErrorType.concept_gap
    return ErrorType.evidence_misread


def _looks_numeric(value: str) -> bool:
    try:
        float(value.strip().replace(",", ""))
    except ValueError:
        return False
    return True


# A concept the student has not got is worth more attention than a slip they have.
_URGENT_ERRORS = {
    ErrorType.concept_gap: Urgency.fundamental,
    ErrorType.formula_error: Urgency.fundamental,
    ErrorType.grammar_rule_gap: Urgency.fundamental,
    ErrorType.trap_answer: Urgency.very_important,
    ErrorType.evidence_misread: Urgency.very_important,
    ErrorType.misread_question: Urgency.very_important,
}


# Words too common to mean two things are about the same idea. Without this,
# a concept titled "Reading the question" collects the entire bank.
_EMPTY_WORDS = frozenset(
    {
        "student",
        "question",
        "questions",
        "answer",
        "answers",
        "because",
        "reading",
        "writing",
        "before",
        "should",
        "always",
        "never",
    }
)


def _match_concepts(mistake: MistakeInput, topic: str) -> list[str]:
    """Which of the student's concepts this question looks like an instance of.

    Offline, so this is a shared-word test rather than a reading: a distinctive
    word of six letters or more, from the concept's title, appearing in the
    question or the topic. Crude on purpose and strict on purpose - a stub that
    files everything would teach the student to distrust the filing.
    """
    if not mistake.known_concepts:
        return []
    haystack = f"{mistake.question_text} {topic} {mistake.student_note or ''}".lower()
    matched: list[str] = []
    for concept in mistake.known_concepts:
        words = {
            word.lower()
            for word in re.findall(r"[A-Za-z]{6,}", concept.title)
            if word.lower() not in _EMPTY_WORDS
        }
        if words and any(word in haystack for word in words):
            matched.append(concept.title)
    return matched[:4]


class StubAnalyzer:
    name = "stub"

    async def analyze(self, mistake: MistakeInput) -> MistakeAnalysis:
        topic = _guess_topic(mistake.question_text, mistake.section)
        error_type = _guess_error_type(mistake)
        return MistakeAnalysis(
            concepts=_match_concepts(mistake, topic),
            error_type=error_type,
            urgency=_URGENT_ERRORS.get(error_type, Urgency.important),
            topic=topic,
            difficulty=Difficulty.medium,
            why_wrong=(
                f"You answered {mistake.your_answer!r} where the answer is "
                f"{mistake.correct_answer!r}. (Offline analyzer: set AI_PROVIDER=claude "
                "for a real explanation.)"
            ),
            correct_reasoning=(
                f"Work the {topic} step that separates {mistake.correct_answer!r} from "
                f"{mistake.your_answer!r}, then check it against the question stem."
            ),
            takeaway=f"Re-read the stem before committing on {topic} questions.",
            trap=f"{mistake.your_answer!r} is the answer you reach if you stop one step early.",
            # Offline, but still deterministic and still *reusing*: the title is
            # derived from the topic, so two questions in one topic land under one
            # pattern and the clustering path is exercised by the tests.
            patterns=[
                PatternTag(
                    title=f"Stopped one step early on {topic}",
                    why=(
                        f"You reached {mistake.your_answer!r} and stopped, where "
                        f"{mistake.correct_answer!r} needed one more step."
                    ),
                )
            ],
        )

    async def interpret(self, question: str, today: date, vocabulary: Vocabulary) -> BankQuery:
        return _interpret(question, today, vocabulary)

    async def summarise(self, question: str, digest: str) -> str:
        """Reports the counts it was given. It does not attempt to answer.

        When the question is about repetition, the repetition block is the part
        worth showing - which is also what a real provider is asked to lead with.
        """
        lines = digest.splitlines()
        rows_at = lines.index("Rows:") if "Rows:" in lines else len(lines)
        head = [line for line in lines[:rows_at] if line.strip()]

        asked_about_repetition = any(
            word in question.lower()
            for word in ("consistent", "always", "keep", "again", "repeat", "recurring")
        )
        if asked_about_repetition:
            # Breadth lines too - several different questions in one area is the
            # commoner pattern, and the one the student's own example described.
            # "Worst offenders" because the question was "which questions": a tally
            # alone leaves them still looking.
            repeats = [
                line
                for line in head
                if "repeat miss" in line
                or "missed again" in line
                or "different questions" in line
                or line.startswith("Worst offenders")
                or "accounts for more than one question" in line
            ]
            if repeats:
                return "\n".join([head[0], *repeats])
        return "\n".join(head)

    async def file_questions(self, concepts: list[ConceptBrief], digest: str) -> Filing:
        """Files on a shared word rather than on understanding.

        Deliberately crude and deliberately strict: it matches a question only
        when a distinctive word from the concept's title appears in the row. That
        keeps the offline app honest - it files almost nothing - while still
        exercising the path end to end.
        """
        rows = {
            match.group(1): match.group(0)
            for match in re.finditer(r"id=([0-9a-f]{32})\b.*", digest)
        }
        matches: list[ConceptMatch] = []
        for concept in concepts:
            words = [
                word.lower()
                for word in re.findall(r"[A-Za-z]{6,}", concept.title)
                if word.lower() not in ("student", "question", "answer", "because")
            ]
            if not words:
                continue
            hits = [
                mistake_id
                for mistake_id, row in rows.items()
                if any(word in row.lower() for word in words)
            ]
            if hits:
                matches.append(ConceptMatch(concept_title=concept.title, mistake_ids=hits))
        return Filing(matches=matches)

    async def read_video(self, video: VideoInput) -> VideoSummary:
        """Splits the transcript on its timestamps rather than understanding it.

        Enough for the pipeline - upload, concepts, tabs, links - to be exercised
        offline, and clearly labelled so nobody mistakes it for a reading.
        """
        stamps = re.findall(r"\[(\d+)s\]", video.transcript)
        lines = [line for line in video.transcript.splitlines() if line.strip()]
        concepts = [
            VideoConcept(
                title=f"Part {index + 1} of {video.title or 'this video'}",
                body=line[:400],
                start_seconds=int(stamps[index]) if index < len(stamps) else None,
            )
            for index, line in enumerate(lines[:3])
        ]
        return VideoSummary(
            summary=(
                "Read by the offline reader, which splits the transcript up rather "
                "than understanding it. Set AI_PROVIDER to get real concepts."
            ),
            concepts=concepts,
        )

    async def propose_concept(self, pattern: str, summary: str, digest: str) -> ConceptProposal:
        """Composes the case from the counts it was given rather than inventing one."""
        count = digest.split(" question", 1)[0].strip() or "Several"
        return ConceptProposal(
            title=pattern,
            why_a_concept=(
                f"{count} questions have collected under this habit, which is enough "
                "for it to be the thing to revise rather than any one of them."
            ),
            what_went_wrong=summary or "The same step went missing each time.",
            body=(
                f"{pattern}. Written offline, so this is the habit's own wording "
                "rather than a reading of the questions - set AI_PROVIDER to get the "
                "real one."
            ),
        )

    async def discuss(self, context: str, conversation: list[Turn]) -> str:
        """Says what it is rather than pretending to tutor.

        The offline stub cannot answer a follow-up, and a plausible-sounding
        non-answer about the student's own mistake is the worst thing it could
        produce - they would revise from it. So it hands back the part of the
        debrief that is most likely to hold the answer and names itself.
        """
        asked = next(
            (turn.text for turn in reversed(conversation) if turn.role == "student"),
            "",
        )
        wanted = "takeaway" if "takeaway" in asked.lower() else "why"
        lines = [line for line in context.splitlines() if line.strip()]
        picked = [line for line in lines if line.lower().startswith(wanted)]
        return "\n".join(
            [
                "The offline reader cannot answer follow-up questions - it has no "
                "model behind it. Set AI_PROVIDER to use a real one.",
                "",
                "From the debrief already written for this question:",
                *(picked or lines[:4]),
            ]
        )


# --- Asking the bank, offline -------------------------------------------------
#
# Keyword matching, not understanding. It covers the phrasings the app's own copy
# uses so the assistant is demonstrable without a key; anything subtler needs a
# real provider.

_URGENCY_WORDS = (
    ("fundamental", Urgency.fundamental),
    ("very important", Urgency.very_important),
    ("important", Urgency.important),
)

_SECTION_WORDS = (
    ("reading", Section.reading_writing),
    ("writing", Section.reading_writing),
    ("verbal", Section.reading_writing),
    ("english", Section.reading_writing),
    ("math", Section.math),
)

_UNITS = {
    "day": 1,
    "week": 7,
    "month": 30,
    "year": 365,
}

_NUMBER_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "nine": 9,
    "twelve": 12,
}


# Words too common to be evidence that the student meant a particular topic.
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "for",
    "from",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "questions",
    "show",
    "that",
    "the",
    "to",
    "what",
    "which",
    "with",
}


def _mentions(text: str, phrase: str) -> bool:
    """Does the question refer to this topic or concept?

    Whole phrase, or every meaningful word of it - so "circles" matches "circles"
    and "command of evidence" matches "evidence command", but a concept titled
    "Read the question" is not dragged in by the word "the".
    """
    phrase = phrase.lower().strip()
    if not phrase:
        return False
    if phrase in text:
        return True
    words = [word for word in re.findall(r"[a-z]+", phrase) if word not in _STOPWORDS]
    return bool(words) and all(word in text for word in words)


def _since(text: str, today: date) -> date | None:
    """'in the past 3 months' / 'last two weeks' -> an absolute date."""
    # The count is optional: "the past year" means one of them.
    match = re.search(r"(?:past|last|previous|within)\s+(?:(\w+)\s+)?(day|week|month|year)s?", text)
    if not match:
        return None
    raw, unit = match.groups()
    count = 1 if raw is None else (int(raw) if raw.isdigit() else _NUMBER_WORDS.get(raw))
    return None if count is None else today - timedelta(days=count * _UNITS[unit])


def _interpret(question: str, today: date, vocabulary: Vocabulary) -> BankQuery:
    text = question.lower()

    urgency = []
    for word, level in _URGENCY_WORDS:
        if word in text:
            urgency.append(level)
            # "very important" contains "important"; the longer phrase wins.
            break

    sections = {level for word, level in _SECTION_WORDS if word in text}

    error_types = [member for member in ErrorType if member.value.replace("_", " ") in text]

    # Match against what the bank actually holds rather than a hardcoded list: the
    # student's own topics and concept titles are the words they will use.
    topics = [topic for topic in vocabulary.topics if _mentions(text, topic)]
    concepts = [title for title in vocabulary.concepts if _mentions(text, title)]

    return BankQuery(
        urgency=urgency,
        section=sorted(sections),
        error_type=error_types,
        topics=topics,
        concepts=concepts,
        logged_after=_since(text, today),
        only_due=("due" in text or "review now" in text),
        sort="most_urgent" if "urgent" in text else "newest",
    )
