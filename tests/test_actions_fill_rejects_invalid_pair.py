from atlas.cli import run_actions_fill
from atlas.models.tasks import Task, TaskList
from atlas.storage.sqlite import connect, init_db, insert_pending_action, list_pending_actions, upsert_task_lists, upsert_tasks


def test_actions_fill_rejects_invalid_pair(tmp_path):
    db_path = tmp_path / "atlas.db"
    conn = connect(db_path)
    try:
        init_db(conn)
        upsert_task_lists(conn, [TaskList(id="list-1", title="Primary")])
        upsert_tasks(
            conn,
            "list-1",
            [Task(id="t1", title="Finish report", status="needsAction")],
        )
        action_id = insert_pending_action(
            conn,
            "atlas",
            "request_more_info",
            {
                "action": {
                    "question": "Which task should I mark complete?",
                    "needed_fields": ["list_id", "task_id"],
                },
                "reason": "Missing identifiers.",
                "source_head": "Operations",
            },
        )
    finally:
        conn.close()

    exit_code = run_actions_fill(
        str(db_path),
        action_id=action_id,
        task_id="missing",
        list_id="list-1",
        auto=False,
    )
    assert exit_code == 2

    conn = connect(db_path)
    try:
        init_db(conn)
        rows = list_pending_actions(conn, status="pending", limit=10)
    finally:
        conn.close()

    assert len(rows) == 1
    assert rows[0]["action_type"] == "request_more_info"
