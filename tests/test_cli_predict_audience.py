from atlas.cli import run_predict_audience
from atlas.storage.sqlite import connect, get_latest_audience_forecast, init_db


def test_predict_audience_stub_persists(tmp_path, capsys):
    db_path = tmp_path / "atlas.db"
    msg = tmp_path / "announcement.md"
    msg.write_text("We are restructuring the team next quarter.", encoding="utf-8")

    exit_code = run_predict_audience(
        str(db_path),
        [str(msg)],
        "How will staff react to this reorg?",
        enable_prediction=False,
        project_name=None,
        context=None,
    )
    assert exit_code == 0

    out = capsys.readouterr().out
    assert "MiroFish Audience Reaction" in out
    assert "Reaction risk:" in out

    conn = connect(db_path)
    try:
        init_db(conn)
        forecast = get_latest_audience_forecast(conn)
    finally:
        conn.close()
    assert forecast is not None
    assert forecast["requirement"] == "How will staff react to this reorg?"


def test_predict_audience_missing_file(tmp_path):
    db_path = tmp_path / "atlas.db"
    exit_code = run_predict_audience(
        str(db_path),
        [str(tmp_path / "nope.md")],
        "req",
        enable_prediction=False,
        project_name=None,
        context=None,
    )
    assert exit_code == 2
