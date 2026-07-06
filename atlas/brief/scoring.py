from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from atlas.models.calendar import CalendarEvent


@dataclass(frozen=True)
class Priority:
    title: str
    score: int
    sources: list[str]
    rationale: str


def _tokenize(text: str) -> set[str]:
    return {token.strip(".,:;!?()").lower() for token in text.split() if token.strip()}


def _count_related_events(goal: str, events: Iterable[CalendarEvent]) -> int:
    goal_tokens = _tokenize(goal)
    if not goal_tokens:
        return 0
    related = 0
    for event in events:
        if goal_tokens & _tokenize(event.title):
            related += 1
    return related


def score_priorities(
    goals: list[str],
    events: list[CalendarEvent],
    focus_minutes: int,
) -> list[Priority]:
    priorities: list[Priority] = []
    focus_hours = max(0, round(focus_minutes / 60, 1))
    for index, goal in enumerate(goals):
        related = _count_related_events(goal, events)
        base = 50
        score = base + (2 - index) * 2 + related * 10
        sources = ["Active goal"]
        if related:
            sources.append(f"Calendar: {related} related events")
        sources.append(f"Time constraint: {focus_hours}h focus")
        rationale = (
            f"Score {score} based on goal priority, "
            f"{related} related events, and {focus_hours}h focus available."
        )
        priorities.append(
            Priority(
                title=goal,
                score=score,
                sources=sources,
                rationale=rationale,
            )
        )
    return sorted(priorities, key=lambda item: item.score, reverse=True)
