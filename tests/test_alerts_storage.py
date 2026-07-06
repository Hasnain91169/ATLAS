from atlas.risk.alerts import build_alert
from atlas.storage.sqlite import connect, get_alerts_for_context, init_db, insert_alerts


def test_insert_and_fetch_alerts_by_context(tmp_path):
    conn = connect(tmp_path / "atlas.db")
    try:
        init_db(conn)
        alert = build_alert(
            severity="HIGH",
            category="burnout",
            title="Burnout risk detected",
            triggers=["Meeting load 360m"],
            threshold="Meeting minutes >= 240",
            mitigation="Reduce meetings",
            payload={"example": True},
        )
        insert_alerts(conn, "daily_brief", 1, [alert])
        rows = get_alerts_for_context(conn, "daily_brief", 1)
    finally:
        conn.close()

    assert len(rows) == 1
    assert rows[0]["category"] == "burnout"
