from atlas.cli import run_actions_approve, run_actions_propose
from atlas.storage.sqlite import connect, init_db, list_pending_actions
from atlas.tasks.stub import StubTasksAdapter


def test_cli_actions_flow(tmp_path, monkeypatch):
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
                "payload": {"list_id": "list-1", "task_id": "task-1"},
                "reason": "Test approval",
                "source_head": "Operations",
            }
        ],
    }

    def fake_pipeline(db_path_arg, enable_llm):
        return synthesis, []

    monkeypatch.setattr("atlas.cli._run_org_pipeline", fake_pipeline)

    run_actions_propose(str(db_path), enable_llm=True)

    conn = connect(db_path)
    try:
        init_db(conn)
        actions = list_pending_actions(conn)
    finally:
        conn.close()

    assert len(actions) == 1
    action_id = actions[0]["id"]

    stub = StubTasksAdapter()

    def fake_from_env():
        return stub

    monkeypatch.setattr("atlas.cli.GoogleTasksAdapter.from_env", fake_from_env)

    exit_code = run_actions_approve(str(db_path), action_id)
    assert exit_code == 0
    assert stub.completed == [("list-1", "task-1")]
