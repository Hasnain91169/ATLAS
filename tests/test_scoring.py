from datetime import datetime, timezone

from atlas.brief.scoring import score_priorities
from atlas.models.calendar import CalendarEvent


def test_score_priorities_prefers_related_events():
    goals = ["Write weekly report", "Deep work session", "Admin cleanup"]
    events = [
        CalendarEvent(
            title="Deep work planning",
            start=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 9, 30, tzinfo=timezone.utc),
        )
    ]

    priorities = score_priorities(goals, events, focus_minutes=180)

    assert priorities[0].title == "Deep work session"
