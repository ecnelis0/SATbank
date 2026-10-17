"""Where the points are going: the asked-for questions grouped by why they were lost.

The database does the grouping and the counting - by the reason each debrief
filed the question under, and by the recurring patterns it named. The model is
handed those groups and only writes the *why* for each, so a list under a
heading is always exactly the questions that belong there.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DebriefTurn, Mistake
from .query import overview, times_missed_again
from .report import ERROR_TYPE_LABELS

# Groups shown at most. Past this the panel is a wall, and the tail is groups of
# one or two that say little about a habit.
MAX_GROUPS = 8


@dataclass
class Group:
    key: str
    kind: str  # "reason" or "pattern"
    label: str
    mistakes: list[Mistake]
    repeat_misses: int


def group_mistakes(mistakes: list[Mistake]) -> list[Group]:
    by_reason: dict[str, list[Mistake]] = defaultdict(list)
    by_pattern: dict[str, list[Mistake]] = defaultdict(list)
    for mistake in mistakes:
        if mistake.error_type:
            by_reason[mistake.error_type].append(mistake)
        for pattern in mistake.patterns:
            by_pattern[pattern.title].append(mistake)

    groups = [
        Group(
            key=f"reason:{reason}",
            kind="reason",
            label=ERROR_TYPE_LABELS.get(reason, reason),
            mistakes=items,
            repeat_misses=sum(times_missed_again(m) for m in items),
        )
        for reason, items in by_reason.items()
    ]
    # A pattern under one question is not yet a pattern.
    groups += [
        Group(
            key=f"pattern:{title}",
            kind="pattern",
            label=title,
            mistakes=items,
            repeat_misses=sum(times_missed_again(m) for m in items),
        )
        for title, items in by_pattern.items()
        if len(items) > 1
    ]
    # Most points lost first: questions in the group, then repeat misses. On a tie
    # the reason leads - it is the answer to "why", and the pattern its detail.
    groups.sort(
        key=lambda g: (-len(g.mistakes), -g.repeat_misses, g.kind != "reason", g.label)
    )
    return groups[:MAX_GROUPS]


async def render(
    session: AsyncSession, question: str, groups: list[Group], mistakes: list[Mistake]
) -> str:
    ids = {m.id for g in groups for m in g.mistakes}
    said: dict[str, list[str]] = defaultdict(list)
    if ids:
        rows = await session.execute(
            select(DebriefTurn.mistake_id, DebriefTurn.text)
            .where(DebriefTurn.mistake_id.in_(ids), DebriefTurn.role == "student")
            .order_by(DebriefTurn.created_at)
        )
        for mistake_id, text in rows:
            said[mistake_id].append(text)

    lines = [
        f"The student asked: {question}",
        "",
        f"Counts across all {len(mistakes)} matched question(s):",
        overview(mistakes),
        "",
        "The groups, counted by the database:",
    ]
    for group in groups:
        lines.append(
            f"\nkey={group.key} [{group.kind}] {group.label}: {len(group.mistakes)} "
            f"question(s), missed again on review {group.repeat_misses} time(s)"
        )
        for m in group.mistakes[:12]:
            lines.append(
                f'  - [{m.section}] topic={m.topic or "-"} question="{m.question_text[:140]}" '
                f"you_put={m.your_answer[:40]!r} answer={m.correct_answer[:40]!r}"
            )
            if m.headline:
                lines.append(f"      debrief: {m.headline[:200]}")
            if m.student_note:
                lines.append(f"      what happened, in their words: {m.student_note[:200]}")
            for text in said.get(m.id, [])[-2:]:
                lines.append(f"      they told the debrief: {text[:200]}")
    return "\n".join(lines)
