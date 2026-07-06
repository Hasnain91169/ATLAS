from datetime import date, datetime, time, timezone

from atlas.models.calendar import CalendarEvent
from atlas.models.core import AtlasConfig, WorkingHours
from atlas.workflows.hourly_planner import generate_hourly_plan


def test_hourly_plan_respects_meetings_and_overload():
    config = AtlasConfig(
        timezone="UTC",
        working_hours=WorkingHours(start=time(9, 0), end=time(12, 0)),
        goals=["Goal A", "Goal B", "Goal C"],
    )
    day = date(2025, 1, 1)
    events = [
        CalendarEvent(
            title="Team sync",
            start=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 11, 30, tzinfo=timezone.utc),
        )
    ]

    plan = generate_hourly_plan(config, events, day, timezone.utc)

    assert any(block["kind"] == "meeting" for block in plan.payload["blocks"])
    assert any("Overloaded" in warning for warning in plan.warnings)
    for block in plan.payload["blocks"]:
        start = datetime.fromisoformat(block["start"])
        end = datetime.fromisoformat(block["end"])
        assert start.time() >= time(9, 0)
        assert end.time() <= time(12, 0)
