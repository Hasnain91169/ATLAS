import json

from atlas.models.tasks import Task, TaskList
from atlas.cli import run_tasks_list
from atlas.storage.sqlite import connect, init_db, upsert_task_lists, upsert_tasks


def test_tasks_list_json(tmp_path, capsys):
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
    finally:
        conn.close()

    exit_code = run_tasks_list(
        str(db_path),
        list_id=None,
        status="needsAction",
        search=None,
        due_before=None,
        due_after=None,
        limit=10,
        as_json=True,
    )
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0
    assert payload[0]["id"] == "t1"
    assert payload[0]["list_id"] == "list-1"
