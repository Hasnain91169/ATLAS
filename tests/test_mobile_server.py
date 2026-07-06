import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from atlas.mobile.server import create_server
from atlas.models.tasks import Task, TaskList
from atlas.storage.sqlite import (
    connect,
    init_db,
    insert_daily_brief,
    upsert_task_lists,
    upsert_tasks,
)


def _start_server(db_path, token):
    server = create_server("127.0.0.1", 0, db_path, token)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_server_auth_and_latest_daily_brief(tmp_path):
    db_path = tmp_path / "atlas.db"
    conn = connect(db_path)
    try:
        init_db(conn)
        insert_daily_brief(conn, "2025-01-01", "# Brief", ["test"])
        upsert_task_lists(conn, [TaskList(id="list-1", title="Main")])
        upsert_tasks(
            conn,
            "list-1",
            [
                Task(id="task-1", title="Review notes", status="needsAction"),
            ],
        )
    finally:
        conn.close()

    server, _ = _start_server(db_path, "secret-token")
    host, port = server.server_address
    base_url = f"http://{host}:{port}"

    try:
        req = Request(f"{base_url}/health")
        with urlopen(req) as response:
            assert response.status == 200

        req = Request(f"{base_url}/api/v1/status")
        try:
            urlopen(req)
            assert False, "Expected unauthorized"
        except HTTPError as exc:
            assert exc.code == 401

        req = Request(f"{base_url}/api/v1/status")
        req.add_header("X-ATLAS-TOKEN", "secret-token")
        with urlopen(req) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert "tasks" in payload
            assert {"last_sync", "list_count", "task_count"}.issubset(payload["tasks"])

        req = Request(f"{base_url}/api/v1/latest/daily-brief")
        req.add_header("X-ATLAS-TOKEN", "secret-token")
        with urlopen(req) as response:
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["data"]["markdown"] == "# Brief"

        req = Request(f"{base_url}/api/v1/tasks")
        try:
            urlopen(req)
            assert False, "Expected unauthorized"
        except HTTPError as exc:
            assert exc.code == 401

        req = Request(f"{base_url}/api/v1/tasks?status=needsAction&limit=5")
        req.add_header("X-ATLAS-TOKEN", "secret-token")
        with urlopen(req) as response:
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["tasks"][0]["title"] == "Review notes"

        req = Request(f"{base_url}/client/")
        with urlopen(req) as response:
            assert response.status == 200
            assert "text/html" in response.headers.get("Content-Type", "")

        req = Request(f"{base_url}/client")
        with urlopen(req) as response:
            assert response.status == 200
            assert response.geturl().endswith("/client/")
    finally:
        server.shutdown()
