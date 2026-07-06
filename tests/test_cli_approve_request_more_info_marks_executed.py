from atlas.cli import run_actions_approve
from atlas.storage.sqlite import (
    connect,
    get_pending_action,
    init_db,
    insert_pending_action,
)


def test_cli_approve_request_more_info_marks_executed(tmp_path, capsys):
    db_path = tmp_path / "atlas.db"
    conn = connect(db_path)
    try:
        init_db(conn)
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

    exit_code = run_actions_approve(str(db_path), action_id)
    output = capsys.readouterr().out

    conn = connect(db_path)
    try:
        init_db(conn)
        action = get_pending_action(conn, action_id)
    finally:
        conn.close()

    assert exit_code == 0
    assert action["status"] == "executed"
    assert "Which task should I mark complete?" in output
