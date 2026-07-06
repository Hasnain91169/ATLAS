from datetime import datetime, timezone

from atlas.models.tasks import Task, TaskList
from atlas.storage.sqlite import connect, init_db, list_tasks, upsert_task_lists, upsert_tasks


def test_task_upsert_and_list_filters(tmp_path):
    db_path = tmp_path / "atlas.db"
    conn = connect(db_path)
    try:
        init_db(conn)
        upsert_task_lists(conn, [TaskList(id="list-1", title="Main")])
        now = datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc).isoformat()
        tasks = [
            Task(
                id="task-1",
                title="First task",
                status="needsAction",
                due="2025-01-02T10:00:00Z",
                updated=now,
            ),
            Task(
                id="task-2",
                title="Second task",
                status="completed",
                due="2025-01-03T10:00:00Z",
                updated=now,
            ),
        ]
        upsert_tasks(conn, "list-1", tasks)
        rows = list_tasks(conn, list_id="list-1", status="needsAction", limit=10)
        assert len(rows) == 1
        assert rows[0]["title"] == "First task"

        rows = list_tasks(conn, due_before="2025-01-02T23:59:59Z", status="all", limit=10)
        assert len(rows) == 1
        assert rows[0]["id"] == "task-1"
    finally:
        conn.close()
