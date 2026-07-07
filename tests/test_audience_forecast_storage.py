from atlas.prediction.models import PredictionResult
from atlas.storage.sqlite import (
    connect,
    get_latest_audience_forecast,
    init_db,
    insert_audience_forecast,
)


def _result(verdict="HIGH", score=0.8):
    return PredictionResult(
        report_markdown="# Report",
        outline="A; B",
        verdict=verdict,
        risk_score=score,
        simulation_id="sim-1",
        report_id="rep-1",
        raw={"engine": "stub"},
    )


def test_audience_forecast_round_trip(tmp_path):
    db_path = tmp_path / "atlas.db"
    conn = connect(db_path)
    try:
        init_db(conn)
        assert get_latest_audience_forecast(conn) is None

        insert_audience_forecast(conn, "Q1", _result("LOW", 0.1))
        insert_audience_forecast(conn, "Q2", _result("HIGH", 0.85))

        latest = get_latest_audience_forecast(conn)
        assert latest["requirement"] == "Q2"
        assert latest["verdict"] == "HIGH"
        assert latest["risk_score"] == 0.85
        assert latest["simulation_id"] == "sim-1"
        assert latest["raw"] == {"engine": "stub"}
    finally:
        conn.close()
