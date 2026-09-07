"""Offline analyzer.

Runs with no API key so the whole loop - log, analyse, bank, review - works before
a provider is picked, and so tests never touch the network. Its text is obviously
canned; it is not meant to teach anyone anything.
"""

from __future__ import annotations

from ..models import Difficulty, ErrorType, Urgency
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
