from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from atlas.models.tasks import Task, TaskList
from atlas.storage.schema import CREATE_TABLES, SCHEMA_VERSION

if TYPE_CHECKING:
    from atlas.prediction.models import PredictionResult


def default_db_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return (Path(base) / "atlas" / "atlas.db").resolve()
    return (Path.home() / ".atlas" / "atlas.db").resolve()


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    if current_version < SCHEMA_VERSION:
        conn.executescript(CREATE_TABLES)
        _ensure_task_item_list_id(conn)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()


def _ensure_task_item_list_id(conn: sqlite3.Connection) -> None:
    table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='task_item'"
    ).fetchone()
    if not table:
        return
    columns = conn.execute("PRAGMA table_info(task_item)").fetchall()
    column_names = {column["name"] for column in columns}
    if "list_id" not in column_names:
        conn.execute("ALTER TABLE task_item ADD COLUMN list_id TEXT")


def insert_system_log(conn: sqlite3.Connection, message: str) -> str:
    timestamp = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO system_log (timestamp, message) VALUES (?, ?)",
        (timestamp, message),
    )
    conn.commit()
    return timestamp


def get_latest_system_log(conn: sqlite3.Connection) -> dict[str, str] | None:
    row = conn.execute(
        "SELECT id, timestamp, message FROM system_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "timestamp": row["timestamp"], "message": row["message"]}


def insert_daily_brief(
    conn: sqlite3.Connection, day: str, markdown: str, tags: list[str]
) -> int:
    timestamp = datetime.now(timezone.utc).isoformat()
    tags_blob = ",".join(tags)
    cursor = conn.execute(
        "INSERT INTO daily_brief (timestamp, date, markdown, tags) VALUES (?, ?, ?, ?)",
        (timestamp, day, markdown, tags_blob),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_latest_daily_brief(conn: sqlite3.Connection) -> dict[str, str] | None:
    row = conn.execute(
        "SELECT id, timestamp, date, markdown, tags FROM daily_brief ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "timestamp": row["timestamp"],
        "date": row["date"],
        "markdown": row["markdown"],
        "tags": row["tags"],
    }


def insert_board_report(
    conn: sqlite3.Connection,
    week_start_date: str,
    raw_markdown: str,
    json_payload: str,
    tags: list[str],
) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    tags_blob = ",".join(tags)
    cursor = conn.execute(
        "INSERT INTO board_report (created_at, week_start_date, raw_markdown, json_payload, tags) "
        "VALUES (?, ?, ?, ?, ?)",
        (created_at, week_start_date, raw_markdown, json_payload, tags_blob),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_latest_board_report(conn: sqlite3.Connection) -> dict[str, str] | None:
    row = conn.execute(
        "SELECT id, created_at, week_start_date, raw_markdown, json_payload, tags "
        "FROM board_report ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "week_start_date": row["week_start_date"],
        "raw_markdown": row["raw_markdown"],
        "json_payload": row["json_payload"],
        "tags": row["tags"],
    }


def get_alerts_summary(conn: sqlite3.Connection) -> dict[str, object]:
    row = conn.execute(
        "SELECT MAX(created_at) AS latest, COUNT(*) AS count FROM alerts"
    ).fetchone()
    if row is None:
        return {"latest": None, "count": 0}
    return {"latest": row["latest"], "count": row["count"]}


def insert_alerts(
    conn: sqlite3.Connection,
    context_type: str,
    context_id: int | str,
    alerts: list,
) -> list[str]:
    created_at = datetime.now(timezone.utc).isoformat()
    created_list: list[str] = []
    for alert in alerts:
        tags_blob = ",".join(alert.tags)
        payload_blob = json.dumps(alert.payload, sort_keys=True)
        conn.execute(
            "INSERT INTO alerts (created_at, context_type, context_id, severity, category, "
            "title, message_markdown, status, tags, json_payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                created_at,
                context_type,
                context_id,
                alert.severity,
                alert.category,
                alert.title,
                alert.message_markdown,
                alert.status,
                tags_blob,
                payload_blob,
            ),
        )
        created_list.append(created_at)
    conn.commit()
    return created_list


def list_alerts(
    conn: sqlite3.Connection,
    severity: str | None = None,
    category: str | None = None,
    limit: int = 20,
) -> list[dict[str, str]]:
    query = (
        "SELECT id, created_at, context_type, context_id, severity, category, title, "
        "message_markdown, status, tags, json_payload "
        "FROM alerts WHERE status = 'DRAFT'"
    )
    params: list[object] = []
    if severity:
        query += " AND severity = ?"
        params.append(severity)
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [
        {
            "id": row["id"],
            "created_at": row["created_at"],
            "context_type": row["context_type"],
            "context_id": row["context_id"],
            "severity": row["severity"],
            "category": row["category"],
            "title": row["title"],
            "message_markdown": row["message_markdown"],
            "status": row["status"],
            "tags": row["tags"],
            "json_payload": row["json_payload"],
        }
        for row in rows
    ]


def get_alerts_for_context(
    conn: sqlite3.Connection,
    context_type: str,
    context_id: int | str,
) -> list[dict[str, str]]:
    rows = conn.execute(
        "SELECT id, created_at, context_type, context_id, severity, category, title, "
        "message_markdown, status, tags, json_payload "
        "FROM alerts WHERE context_type = ? AND context_id = ? ORDER BY id DESC",
        (context_type, context_id),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "created_at": row["created_at"],
            "context_type": row["context_type"],
            "context_id": row["context_id"],
            "severity": row["severity"],
            "category": row["category"],
            "title": row["title"],
            "message_markdown": row["message_markdown"],
            "status": row["status"],
            "tags": row["tags"],
            "json_payload": row["json_payload"],
        }
        for row in rows
    ]


def insert_hourly_plan(
    conn: sqlite3.Connection,
    day: str,
    raw_markdown: str,
    json_payload: str,
    tags: list[str],
) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    tags_blob = ",".join(tags)
    cursor = conn.execute(
        "INSERT INTO hourly_plan (created_at, date, raw_markdown, json_payload, tags) "
        "VALUES (?, ?, ?, ?, ?)",
        (created_at, day, raw_markdown, json_payload, tags_blob),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_latest_hourly_plan(conn: sqlite3.Connection) -> dict[str, str] | None:
    row = conn.execute(
        "SELECT id, created_at, date, raw_markdown, json_payload, tags "
        "FROM hourly_plan ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "date": row["date"],
        "raw_markdown": row["raw_markdown"],
        "json_payload": row["json_payload"],
        "tags": row["tags"],
    }


def insert_triage_report(
    conn: sqlite3.Connection,
    raw_markdown: str,
    json_payload: str,
    tags: list[str],
) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    tags_blob = ",".join(tags)
    cursor = conn.execute(
        "INSERT INTO triage_report (created_at, raw_markdown, json_payload, tags) "
        "VALUES (?, ?, ?, ?)",
        (created_at, raw_markdown, json_payload, tags_blob),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_latest_triage_report(conn: sqlite3.Connection) -> dict[str, str] | None:
    row = conn.execute(
        "SELECT id, created_at, raw_markdown, json_payload, tags "
        "FROM triage_report ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "raw_markdown": row["raw_markdown"],
        "json_payload": row["json_payload"],
        "tags": row["tags"],
    }


def insert_acknowledgement(
    conn: sqlite3.Connection,
    item_type: str,
    item_id: str,
    note: str,
) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO acknowledgements (created_at, item_type, item_id, note) "
        "VALUES (?, ?, ?, ?)",
        (created_at, item_type, item_id, note),
    )
    conn.commit()
    return int(cursor.lastrowid)


def upsert_task_lists(conn: sqlite3.Connection, task_lists: list[TaskList]) -> int:
    updated_at = datetime.now(timezone.utc).isoformat()
    rows = [(item.id, item.title, updated_at) for item in task_lists]
    conn.executemany(
        "INSERT INTO task_list (id, title, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET title = excluded.title, updated_at = excluded.updated_at",
        rows,
    )
    conn.commit()
    return len(rows)


def upsert_tasks(conn: sqlite3.Connection, list_id: str, tasks: list[Task]) -> int:
    rows = []
    for task in tasks:
        raw_json = json.dumps(task.model_dump(exclude={"list_id"}), sort_keys=True)
        rows.append(
            (
                task.id,
                list_id,
                task.title,
                task.notes,
                task.due,
                task.status,
                task.updated,
                task.completed,
                task.parent,
                task.position,
                raw_json,
            )
        )
    conn.executemany(
        "INSERT INTO task_item (id, list_id, title, notes, due, status, updated, completed, parent, position, raw_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET "
        "list_id = excluded.list_id, "
        "title = excluded.title, "
        "notes = excluded.notes, "
        "due = excluded.due, "
        "status = excluded.status, "
        "updated = excluded.updated, "
        "completed = excluded.completed, "
        "parent = excluded.parent, "
        "position = excluded.position, "
        "raw_json = excluded.raw_json",
        rows,
    )
    conn.commit()
    return len(rows)


def insert_task_sync_log(
    conn: sqlite3.Connection, list_count: int, task_count: int, source: str
) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO task_sync_log (created_at, list_count, task_count, source) "
        "VALUES (?, ?, ?, ?)",
        (created_at, list_count, task_count, source),
    )
    conn.commit()
    return int(cursor.lastrowid)


def list_tasks(
    conn: sqlite3.Connection,
    list_id: str | None = None,
    status: str | None = None,
    due_before: str | None = None,
    due_after: str | None = None,
    search: str | None = None,
    limit: int = 20,
) -> list[dict[str, str | None]]:
    query = "SELECT id, list_id, title, notes, due, status, updated, completed FROM task_item WHERE 1=1"
    params: list[object] = []
    if list_id:
        query += " AND list_id = ?"
        params.append(list_id)
    if status and status != "all":
        query += " AND status = ?"
        params.append(status)
    if due_before:
        query += " AND due IS NOT NULL AND due <= ?"
        params.append(due_before)
    if due_after:
        query += " AND due IS NOT NULL AND due >= ?"
        params.append(due_after)
    if search:
        query += " AND (title LIKE ? OR notes LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term])
    query += " ORDER BY COALESCE(due, '9999-12-31T23:59:59Z'), updated DESC, title ASC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [
        {
            "id": row["id"],
            "list_id": row["list_id"],
            "title": row["title"],
            "notes": row["notes"],
            "due": row["due"],
            "status": row["status"],
            "updated": row["updated"],
            "completed": row["completed"],
        }
        for row in rows
    ]


def get_task_by_pair(
    conn: sqlite3.Connection, list_id: str, task_id: str
) -> dict[str, str | None] | None:
    row = conn.execute(
        "SELECT id, list_id, title, notes, due, status, updated, completed "
        "FROM task_item WHERE list_id = ? AND id = ?",
        (list_id, task_id),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "list_id": row["list_id"],
        "title": row["title"],
        "notes": row["notes"],
        "due": row["due"],
        "status": row["status"],
        "updated": row["updated"],
        "completed": row["completed"],
    }


def get_latest_task_sync_summary(conn: sqlite3.Connection) -> dict[str, object]:
    row = conn.execute(
        "SELECT created_at, list_count, task_count FROM task_sync_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return {"created_at": None, "list_count": 0, "task_count": 0}
    return {
        "created_at": row["created_at"],
        "list_count": row["list_count"],
        "task_count": row["task_count"],
    }


def insert_pending_action(
    conn: sqlite3.Connection, source: str, action_type: str, payload: dict
) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    payload_json = json.dumps(payload, sort_keys=True)
    cursor = conn.execute(
        "INSERT INTO pending_action (created_at, source, action_type, payload_json, status) "
        "VALUES (?, ?, ?, ?, ?)",
        (created_at, source, action_type, payload_json, "pending"),
    )
    conn.commit()
    return int(cursor.lastrowid)


def list_pending_actions(
    conn: sqlite3.Connection, status: str = "pending", limit: int = 50
) -> list[dict[str, object]]:
    query = (
        "SELECT id, created_at, source, action_type, payload_json, status, "
        "decided_at, executed_at, error "
        "FROM pending_action"
    )
    params: list[object] = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    results = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        results.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "source": row["source"],
                "action_type": row["action_type"],
                "payload_json": row["payload_json"],
                "payload": payload,
                "status": row["status"],
                "decided_at": row["decided_at"],
                "executed_at": row["executed_at"],
                "error": row["error"],
            }
        )
    return results


def get_pending_action(
    conn: sqlite3.Connection, action_id: int
) -> dict[str, object] | None:
    row = conn.execute(
        "SELECT id, created_at, source, action_type, payload_json, status, "
        "decided_at, executed_at, error "
        "FROM pending_action WHERE id = ?",
        (action_id,),
    ).fetchone()
    if row is None:
        return None
    payload = json.loads(row["payload_json"])
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "source": row["source"],
        "action_type": row["action_type"],
        "payload_json": row["payload_json"],
        "payload": payload,
        "status": row["status"],
        "decided_at": row["decided_at"],
        "executed_at": row["executed_at"],
        "error": row["error"],
    }


def set_pending_action_status(
    conn: sqlite3.Connection,
    action_id: int,
    status: str,
    error: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    fields = ["status = ?"]
    params: list[object] = [status]
    if status in {"approved", "rejected"}:
        fields.append("decided_at = ?")
        params.append(now)
    if status in {"executed", "failed"}:
        fields.append("executed_at = ?")
        params.append(now)
    if error is not None:
        fields.append("error = ?")
        params.append(error)
    params.append(action_id)
    query = f"UPDATE pending_action SET {', '.join(fields)} WHERE id = ?"
    conn.execute(query, params)
    conn.commit()


def insert_audience_forecast(
    conn: sqlite3.Connection, requirement: str, result: "PredictionResult"
) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    raw_json = json.dumps(result.raw, sort_keys=True)
    cursor = conn.execute(
        "INSERT INTO audience_forecast "
        "(created_at, requirement, verdict, risk_score, report_markdown, "
        "simulation_id, report_id, raw_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            created_at,
            requirement,
            result.verdict,
            result.risk_score,
            result.report_markdown,
            result.simulation_id,
            result.report_id,
            raw_json,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def get_latest_audience_forecast(
    conn: sqlite3.Connection,
) -> dict[str, object] | None:
    row = conn.execute(
        "SELECT id, created_at, requirement, verdict, risk_score, report_markdown, "
        "simulation_id, report_id, raw_json "
        "FROM audience_forecast ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "requirement": row["requirement"],
        "verdict": row["verdict"],
        "risk_score": row["risk_score"],
        "report_markdown": row["report_markdown"],
        "simulation_id": row["simulation_id"],
        "report_id": row["report_id"],
        "raw": json.loads(row["raw_json"]),
    }
