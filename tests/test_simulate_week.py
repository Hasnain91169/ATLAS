from datetime import date, time

from atlas.models.core import AtlasConfig, WorkingHours
from atlas.workflows.simulation import simulate_week


def test_simulate_week_two_days(tmp_path):
    config = AtlasConfig(
        timezone="UTC",
        working_hours=WorkingHours(start=time(9, 0), end=time(12, 0)),
        goals=["Goal A", "Goal B", "Goal C"],
    )
    messages_path = tmp_path / "messages.yaml"
    messages_path.write_text(
        "\n".join(
            [
                "- id: 1",
                "  sender: ceo@example.com",
                "  subject: Urgent request",
                "  body: Please respond ASAP.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "atlas.db"
    summary = simulate_week(
        config,
        db_path,
        start_day=date(2025, 1, 1),
        days=2,
        messages_path=messages_path,
    )

    assert summary["daily_brief"]["count"] >= 2
    assert summary["hourly_plan"]["count"] >= 2
    assert summary["board_report"]["count"] >= 1
    assert summary["triage_report"]["count"] >= 1
