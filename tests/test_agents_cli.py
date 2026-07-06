from atlas.cli import run_agents_command
from atlas.storage.sqlite import connect, init_db


def test_agents_cli_placeholder_output(tmp_path, capsys):
    db_path = tmp_path / "atlas.db"
    conn = connect(db_path)
    try:
        init_db(conn)
    finally:
        conn.close()

    exit_code = run_agents_command(str(db_path), enable_llm=False)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "## Operations" in output
    assert "## Risk & Compliance" in output
    assert "## Finance" in output
    assert "## Learning" in output
    assert "LLM disabled" in output
