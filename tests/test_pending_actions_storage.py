from atlas.storage.sqlite import (
    connect,
    init_db,
    insert_pending_action,
    get_pending_action,
    list_pending_actions,
    set_pending_action_status,
)


def test_pending_actions_storage(tmp_path):
    db_path = tmp_path / "atlas.db"
    conn = connect(db_path)
    try:
        init_db(conn)
        action_id = insert_pending_action(
            conn,
            "atlas",
            "task_complete",
            {"action": {"list_id": "list-1", "task_id": "task-1"}},
        )
        rows = list_pending_actions(conn)
        assert len(rows) == 1
        assert rows[0]["id"] == action_id

        action = get_pending_action(conn, action_id)
        assert action["action_type"] == "task_complete"

        set_pending_action_status(conn, action_id, "approved")
        action = get_pending_action(conn, action_id)
        assert action["status"] == "approved"
        assert action["decided_at"] is not None

        set_pending_action_status(conn, action_id, "executed")
        action = get_pending_action(conn, action_id)
        assert action["status"] == "executed"
        assert action["executed_at"] is not None
    finally:
        conn.close()
