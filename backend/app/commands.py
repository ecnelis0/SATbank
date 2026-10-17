"""Telling a question about the debrief apart from an instruction to change it.

In the ask-about-this-question chat the student mostly asks things - "what does
this debrief mean?" - but sometimes tells: "consider this in the debrief", "tag
this as a misread". The second kind should rewrite the debrief, not just get a
chat answer that is forgotten when the page closes.

Words, not a model call: a command has to be recognised the same way every time,
for free, and the chat also carries an explicit "apply to the debrief" button for
anything phrased in a way this does not catch. It errs towards *not* firing - a
question taken for a command would rewrite a debrief nobody asked to change.
"""

from __future__ import annotations

import re

# Asking about the debrief, not telling it. "Is the debrief right?" mentions the
# debrief and is still a question.
_QUESTION_START = re.compile(
    r"^\s*(what|why|how|which|who|where|when|does|did|is|are|was|were|do|should)\b",
    re.IGNORECASE,
)

_MENTIONS_DEBRIEF = re.compile(r"\bdebrief\b", re.IGNORECASE)

_ACTION = re.compile(
    r"\b(consider|add|include|put|use|note|mention|reflect|update|change|rewrite|"
    r"re-?write|redo|re-?do|fix|save|apply|incorporate|factor|account|keep|remember|"
    r"record|tag|file|mark|replace|remove|drop|edit)\w*\b",
    re.IGNORECASE,
)

# "Tag this as a misread", "file it under careless errors" - the debrief is
# implied by the verb, so it need not be named.
_RETAG = re.compile(
    r"^\s*(please\s+)?(re-?)?(tag|file|mark|classify|label)\s+(this|it)\b",
    re.IGNORECASE,
)


def is_debrief_command(text: str) -> bool:
    if _RETAG.search(text):
        return True
    if _QUESTION_START.search(text):
        return False
    return bool(_MENTIONS_DEBRIEF.search(text) and _ACTION.search(text))


# --- asking the bank for a breakdown -------------------------------------------
#
# "What do I keep getting wrong?", "where am I losing points?" - questions about
# *why*, across many questions, rather than for a list of some of them. These get
# the questions grouped by reason and pattern, each group debriefed. A plain
# search ("everything due now") is better served by the flat list.

_BREAKDOWN = re.compile(
    r"\b("
    r"patterns?|habits?|recurring|consistently|again and again|over and over|"
    r"keep (?:on )?(?:getting|making|missing|losing|doing|messing|falling|picking)|"
    r"(?:lose|lost|losing) (?:the most |most |my |more )?points?|"
    r"where (?:do|did|am|have) i (?:lose|lost|losing|go wrong|went wrong|mess)|"
    r"why (?:do|did|am|have) i (?:keep|get|got|getting|miss|lose|make)|"
    r"weak(?:ness|nesses|est| spots?)|struggl\w*|worst at|"
    r"(?:common|most frequent|biggest|main) (?:mistakes?|errors?|problems?|reasons?)|"
    r"go(?:ing)? wrong|reasons? (?:why|i)"
    r")\b",
    re.IGNORECASE,
)


def is_breakdown_question(text: str) -> bool:
    return bool(_BREAKDOWN.search(text))
