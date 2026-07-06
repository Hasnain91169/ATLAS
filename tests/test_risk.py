from atlas.risk.rules import RiskSignals, evaluate_risks


def test_meeting_heavy_triggers_burnout_and_overcommitment():
    signals = RiskSignals(
        meeting_minutes=360,
        focus_minutes=30,
        working_hours_minutes=480,
        priorities_count=4,
    )
    alerts = evaluate_risks(signals)
    categories = {alert.category for alert in alerts}
    assert "burnout" in categories
    assert "overcommitment" in categories
