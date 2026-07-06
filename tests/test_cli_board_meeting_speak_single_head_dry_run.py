from atlas.cli import run_board_meeting_speak
from atlas.storage.sqlite import connect, init_db


def test_cli_board_meeting_speak_single_head_dry_run(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "atlas.db"
    out_dir = tmp_path / "audio"
    conn = connect(db_path)
    try:
        init_db(conn)
    finally:
        conn.close()

    def fail_from_env():
        raise AssertionError("ElevenLabsClient should not be initialized on dry-run")

    monkeypatch.setattr("atlas.cli.ElevenLabsClient.from_env", fail_from_env)

    exit_code = run_board_meeting_speak(
        str(db_path),
        enable_llm=False,
        out_dir=str(out_dir),
        dry_run=True,
        head="operations",
        audio_format="mp3",
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "operations" in output
    assert output.count(".mp3") == 1
