from atlas.cli import run_org
from atlas.storage.sqlite import connect, init_db


def test_org_run_verbose_output(tmp_path, capsys):
    db_path = tmp_path / "atlas.db"
    conn = connect(db_path)
    try:
        init_db(conn)
    finally:
        conn.close()

    exit_code = run_org(str(db_path), enable_llm=False, verbose=True)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "# Head Reports" in output
    assert "## Operations" in output
    assert "- Worker Outputs:" in output
