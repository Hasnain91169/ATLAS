from datetime import date, datetime, time, timezone

from atlas.calendar.stub import StubCalendarAdapter
from atlas.models.core import AtlasConfig, WorkingHours
from atlas.workflows.board_meeting import generate_board_report
from atlas.workflows.hourly_planner import generate_hourly_plan
from atlas.brief.generator import generate_daily_brief


def _config() -> AtlasConfig:
    return AtlasConfig(
        timezone="UTC",
        working_hours=WorkingHours(start=time(9, 0), end=time(12, 0)),
        goals=["Goal A", "Goal B", "Goal C"],
    )


def test_daily_brief_sections_with_stub_calendar():
    config = _config()
    tz = timezone.utc
    day = date(2025, 1, 1)
    events = StubCalendarAdapter().fetch_events(day, tz)
    brief = generate_daily_brief(config, events, day, tz)
    markdown = brief.markdown

    assert "## Today's Schedule" in markdown
    assert "## Top 3 Priorities" in markdown
    assert "## Risk & Compliance" in markdown
    assert "## Suggested Actions" in markdown
    assert "Meeting: Daily standup" in markdown


def test_hourly_plan_sections_with_stub_calendar():
    config = _config()
    tz = timezone.utc
    day = date(2025, 1, 1)
    events = StubCalendarAdapter().fetch_events(day, tz)
    plan = generate_hourly_plan(config, events, day, tz)
    markdown = plan.markdown

    assert "## Hourly Plan" in markdown
    assert "## Ops Warnings" in markdown
    assert "## Risk & Compliance" in markdown
    assert "Overloaded" in markdown


def test_board_meeting_sections_with_fixed_now():
    config = _config()
    now = datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc)
    report = generate_board_report(config, now=now)
    markdown = report.markdown

    assert "## Atlas Executive Summary" in markdown
    assert "## Department Reports" in markdown
    assert "## Risk & Compliance Interruption" in markdown
    assert "## Department Head Drafts (AI)" in markdown
    assert "## Post-Mortem & Learning" in markdown
    assert "## Decisions for Next Week" in markdown
