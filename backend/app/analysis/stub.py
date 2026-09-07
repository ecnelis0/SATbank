"""Offline analyzer.

Runs with no API key so the whole loop - log, analyse, bank, review - works before
a provider is picked, and so tests never touch the network. Its text is obviously
canned; it is not meant to teach anyone anything.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from ..models import Difficulty, ErrorType, Section, Urgency
from ..query import BankQuery
from .base import MistakeAnalysis, MistakeInput

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


class StubAnalyzer:
    name = "stub"

    async def analyze(self, mistake: MistakeInput) -> MistakeAnalysis:
        topic = _guess_topic(mistake.question_text, mistake.section)
        error_type = _guess_error_type(mistake)
        return MistakeAnalysis(
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
            tags=[topic.replace(" ", "-"), mistake.section],
        )

    async def interpret(self, question: str, today: date) -> BankQuery:
        return _interpret(question, today)

    async def summarise(self, question: str, digest: str) -> str:
        first = digest.splitlines()[0]
        return f"{first} (Offline assistant: set AI_PROVIDER=claude for a real answer.)"


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


def _since(text: str, today: date) -> date | None:
    """'in the past 3 months' / 'last two weeks' -> an absolute date."""
    # The count is optional: "the past year" means one of them.
    match = re.search(r"(?:past|last|previous|within)\s+(?:(\w+)\s+)?(day|week|month|year)s?", text)
    if not match:
        return None
    raw, unit = match.groups()
    count = 1 if raw is None else (int(raw) if raw.isdigit() else _NUMBER_WORDS.get(raw))
    return None if count is None else today - timedelta(days=count * _UNITS[unit])


def _interpret(question: str, today: date) -> BankQuery:
    text = question.lower()

    urgency = []
    for word, level in _URGENCY_WORDS:
        if word in text:
            urgency.append(level)
            # "very important" contains "important"; the longer phrase wins.
            break

    sections = {level for word, level in _SECTION_WORDS if word in text}

    error_types = [member for member in ErrorType if member.value.replace("_", " ") in text]

    topics = [topic for topic in (*_MATH_HINTS.values(), *_VERBAL_HINTS.values()) if topic in text]

    return BankQuery(
        urgency=urgency,
        section=sorted(sections),
        error_type=error_types,
        topics=topics,
        logged_after=_since(text, today),
        only_due=("due" in text or "review now" in text),
        sort="most_urgent" if "urgent" in text else "newest",
    )
