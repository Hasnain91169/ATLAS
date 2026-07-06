from datetime import time

from atlas.models.core import AtlasConfig, WorkingHours
from atlas.risk.rules import RiskSignals
from atlas.workflows.board_meeting import generate_board_report


def _config() -> AtlasConfig:
    return AtlasConfig(
        timezone="UTC",
        working_hours=WorkingHours(start=time(9, 0), end=time(17, 0)),
        goals=["Primary objective", "Secondary objective", "Optional objective"],
    )


def test_board_meeting_markdown_sections():
    report = generate_board_report(_config())
    markdown = report.markdown

    assert "## Atlas Executive Summary" in markdown
    assert "## Department Reports" in markdown
    assert "## Risk & Compliance Interruption" in markdown
    assert "## Department Head Drafts (AI)" in markdown
    assert "## Post-Mortem & Learning" in markdown
    assert "## Decisions for Next Week" in markdown


def test_board_meeting_risk_veto_marker():
    signals = RiskSignals(meeting_minutes=360, focus_minutes=30, working_hours_minutes=480)
    report = generate_board_report(_config(), risk_signals=signals)
    assert "Objective downgraded due to risk veto." in report.markdown


def test_board_meeting_agent_bullets(monkeypatch):
    def fake_run_agents(context, enable_llm, llm=None, fail_open=False):
        return {"Operations": "- Already bullet\n1. Numbered item\nPlain line"}

    monkeypatch.setattr("atlas.workflows.board_meeting.run_agents", fake_run_agents)
    report = generate_board_report(_config())
    markdown = report.markdown

    assert "- Already bullet" in markdown
    assert "-- Already bullet" not in markdown
    assert "1. Numbered item" in markdown
    assert "- Plain line" in markdown
