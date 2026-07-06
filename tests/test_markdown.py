from datetime import date, datetime, time, timezone

from atlas.brief.generator import generate_daily_brief
from atlas.models.calendar import CalendarEvent
from atlas.models.core import AtlasConfig, WorkingHours


def test_markdown_contains_schedule_and_sections():
    config = AtlasConfig(
        timezone="UTC",
        working_hours=WorkingHours(start=time(9, 0), end=time(11, 0)),
        goals=["Goal A", "Goal B", "Goal C"],
    )
    day = date(2025, 1, 1)
    events = [
        CalendarEvent(
            title="Standup",
            start=datetime(2025, 1, 1, 9, 30, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
    ]

    brief = generate_daily_brief(config, events, day, timezone.utc)
    markdown = brief.markdown

    assert "## Today's Schedule" in markdown
    assert "- 09:00-09:30 Focus time" in markdown
    assert "- 09:30-10:00 Meeting: Standup" in markdown
    assert "## Top 3 Priorities" in markdown
    assert "## Risk & Compliance" in markdown
    assert "## Suggested Actions" in markdown
