from atlas.cli import run_actions_propose
from atlas.storage.sqlite import connect, init_db, list_pending_actions


def test_actions_propose_skips_invalid_candidate(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "atlas.db"
    conn = connect(db_path)
    try:
        init_db(conn)
    finally:
        conn.close()

    synthesis = {
        "what_mattered": [],
        "what_happens_next": [],
        "approval_candidates": [
            {
                "action_type": "task_complete",
                "payload": {"list_id": "list-1"},
                "reason": "Missing task_id",
                "source_head": "Operations",
            }
        ],
    }

    def fake_pipeline(db_path_arg, enable_llm):
        return synthesis, []

    monkeypatch.setattr("atlas.cli._run_org_pipeline", fake_pipeline)

    run_actions_propose(str(db_path), enable_llm=True)
    output = capsys.readouterr().out
    assert "Skipped invalid candidate" in output

    conn = connect(db_path)
    try:
        init_db(conn)
        actions = list_pending_actions(conn)
    finally:
        conn.close()
    assert actions == []
