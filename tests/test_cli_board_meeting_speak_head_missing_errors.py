from atlas.cli import run_board_meeting_speak


def test_cli_board_meeting_speak_head_missing_errors(monkeypatch, capsys):
    def fake_report(db_path, enable_llm):
        return "# Report\n\n## Atlas Synthesis\n### What mattered\n- None\n\n## Department Head Drafts (AI)\n### Operations\nSummary: Ops\n"

    monkeypatch.setattr("atlas.cli.generate_tts_report", fake_report)

    exit_code = run_board_meeting_speak(
        db_path=None,
        enable_llm=False,
        out_dir=None,
        dry_run=True,
        head="finance",
        audio_format="mp3",
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "Requested head section not found" in (captured.out + captured.err)
