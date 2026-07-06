from atlas.storage.sqlite import (
    connect,
    get_latest_board_report,
    get_latest_system_log,
    get_latest_hourly_plan,
    get_latest_triage_report,
    init_db,
    insert_board_report,
    insert_system_log,
    insert_hourly_plan,
    insert_triage_report,
)


def test_insert_and_retrieve_system_log(tmp_path):
    db_path = tmp_path / "atlas.db"
    conn = connect(db_path)
    try:
        init_db(conn)
        insert_system_log(conn, "boot test")
        row = get_latest_system_log(conn)
    finally:
        conn.close()

    assert row is not None
    assert row["message"] == "boot test"


def test_insert_and_retrieve_board_report(tmp_path):
    db_path = tmp_path / "atlas.db"
    conn = connect(db_path)
    try:
        init_db(conn)
        insert_board_report(
            conn,
            "2025-01-01",
            "# Board Report",
            '{"example": true}',
            ["board-meeting"],
        )
        row = get_latest_board_report(conn)
    finally:
        conn.close()

    assert row is not None
    assert row["raw_markdown"] == "# Board Report"


def test_insert_and_retrieve_hourly_plan(tmp_path):
    db_path = tmp_path / "atlas.db"
    conn = connect(db_path)
    try:
        init_db(conn)
        insert_hourly_plan(
            conn,
            "2025-01-01",
            "# Hourly Plan",
            '{"blocks": []}',
            ["hourly-plan"],
        )
        row = get_latest_hourly_plan(conn)
    finally:
        conn.close()

    assert row is not None
    assert row["raw_markdown"] == "# Hourly Plan"


def test_insert_and_retrieve_triage_report(tmp_path):
    db_path = tmp_path / "atlas.db"
    conn = connect(db_path)
    try:
        init_db(conn)
        insert_triage_report(
            conn,
            "# Triage Report",
            '{"items": []}',
            ["triage"],
        )
        row = get_latest_triage_report(conn)
    finally:
        conn.close()

    assert row is not None
    assert row["raw_markdown"] == "# Triage Report"
