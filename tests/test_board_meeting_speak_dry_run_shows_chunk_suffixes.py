from atlas.cli import run_board_meeting_speak


def test_board_meeting_speak_dry_run_shows_chunk_suffixes(monkeypatch, capsys):
    big = "para\n\n" + ("x" * 3000)

    def fake_report(db_path, enable_llm):
        return (
            "# Report\n\n"
            "## Atlas Synthesis\n### What mattered\n- None\n\n"
            "## Department Head Drafts (AI)\n"
            "### Operations\n"
            f"{big}\n"
        )

    monkeypatch.setattr("atlas.cli.generate_tts_report", fake_report)

    def fail_from_env():
        raise AssertionError("Should not init ElevenLabs on dry-run")

    monkeypatch.setattr("atlas.cli.ElevenLabsClient.from_env", fail_from_env)

    exit_code = run_board_meeting_speak(
        db_path=None,
        enable_llm=False,
        out_dir=None,
        dry_run=True,
        head="operations",
        audio_format="mp3",
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "-01.mp3" in out
    assert "-02.mp3" in out
