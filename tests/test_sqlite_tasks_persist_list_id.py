from atlas.models.tasks import Task, TaskList
from atlas.storage.sqlite import connect, init_db, list_tasks, upsert_task_lists, upsert_tasks


def test_sqlite_tasks_persist_list_id(tmp_path):
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
        rows = list_tasks(conn, list_id="list-1")
    finally:
        conn.close()

    assert rows
    assert rows[0]["list_id"] == "list-1"
