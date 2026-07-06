from atlas.board_meeting.report import generate_board_report
from atlas.storage.sqlite import connect, init_db


def test_board_meeting_report_contains_sections(tmp_path):
    db_path = tmp_path / "atlas.db"
    conn = connect(db_path)
    try:
        init_db(conn)
    finally:
        conn.close()

    report = generate_board_report(str(db_path), enable_llm=False)

    assert "## Atlas Synthesis" in report
    assert "## Department Head Drafts (AI)" in report
    assert "### Operations" in report
    assert "### Risk & Compliance" in report
    assert "### Finance" in report
    assert "### Learning" in report
