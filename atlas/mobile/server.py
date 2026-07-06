from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from atlas.storage.schema import SCHEMA_VERSION
from atlas.storage.sqlite import (
    connect,
    default_db_path,
    get_latest_board_report,
    get_latest_daily_brief,
    get_latest_hourly_plan,
    get_latest_triage_report,
    init_db,
    insert_acknowledgement,
    get_latest_task_sync_summary,
    list_alerts,
    list_tasks,
)

_LOCK = threading.Lock()


class ServerConfig:
    def __init__(self, db_path: Path, token: str, host: str, port: int, allow_lan_cors: bool):
        self.db_path = db_path
        self.token = token
        self.host = host
        self.port = port
        self.allow_lan_cors = allow_lan_cors


def _is_private_host(host: str) -> bool:
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    parts = host.split(".")
    if len(parts) != 4 or not all(part.isdigit() for part in parts):
        return False
    nums = [int(part) for part in parts]
    if nums[0] == 10:
        return True
    if nums[0] == 192 and nums[1] == 168:
        return True
    if nums[0] == 172 and 16 <= nums[1] <= 31:
        return True
    return False


def _origin_allowed(origin: str | None) -> bool:
    if not origin:
        return False
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname
    if not host:
        return False
    return _is_private_host(host)


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    if hasattr(handler, "_cors_headers"):
        handler._cors_headers()
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", 0))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    return json.loads(raw)


def _serve_static(handler: BaseHTTPRequestHandler, base_dir: Path, rel_path: str) -> bool:
    safe_path = (base_dir / rel_path.lstrip("/")).resolve()
    if not str(safe_path).startswith(str(base_dir.resolve())):
        _json_response(handler, HTTPStatus.NOT_FOUND, {"error": "Not found"})
        return True
    if safe_path.is_dir():
        safe_path = safe_path / "index.html"
    if not safe_path.exists():
        return False
    content = safe_path.read_bytes()
    if safe_path.suffix == ".html":
        content_type = "text/html; charset=utf-8"
    elif safe_path.suffix == ".js":
        content_type = "application/javascript; charset=utf-8"
    else:
        content_type = "application/octet-stream"
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(content)))
    handler.end_headers()
    handler.wfile.write(content)
    return True


class AtlasRequestHandler(BaseHTTPRequestHandler):
    server: "AtlasServer"

    def _origin_matches_host(self, origin: str) -> bool:
        parsed = urlparse(origin)
        host_header = self.headers.get("Host")
        if not host_header:
            return False
        return parsed.netloc == host_header

    def _check_auth(self) -> bool:
        token = self.headers.get("X-ATLAS-TOKEN")
        return bool(token) and token == self.server.config.token

    def _cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        if not origin:
            return
        if self.server.config.allow_lan_cors:
            allowed = _origin_allowed(origin)
        else:
            allowed = self._origin_matches_host(origin)
        if allowed:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers", "X-ATLAS-TOKEN, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/client":
            self.send_response(HTTPStatus.MOVED_PERMANENTLY)
            self.send_header("Location", "/client/")
            self.end_headers()
            return

        if self.path.startswith("/client/") or self.path == "/":
            base_dir = Path(__file__).resolve().parents[2] / "static" / "mobile_client"
            rel_path = "index.html" if self.path == "/" else self.path.replace("/client/", "")
            if _serve_static(self, base_dir, rel_path):
                return

        query = parse_qs(parsed.query)

        if path == "/health":
            payload = {"status": "ok"}
            _json_response(self, HTTPStatus.OK, payload)
            return

        if not self._check_auth():
            _json_response(self, HTTPStatus.UNAUTHORIZED, {"error": "Unauthorized"})
            return

        if path == "/api/v1/status":
            with _LOCK:
                conn = self.server._connect()
                try:
                    init_db(conn)
                    task_summary = get_latest_task_sync_summary(conn)
                except Exception:
                    task_summary = {"created_at": None, "list_count": 0, "task_count": 0}
                finally:
                    conn.close()
            payload = {
                "time": self.server.now_iso(),
                "db_path": str(self.server.config.db_path),
                "schema_version": SCHEMA_VERSION,
                "tasks": {
                    "last_sync": task_summary.get("created_at"),
                    "list_count": task_summary.get("list_count", 0),
                    "task_count": task_summary.get("task_count", 0),
                },
            }
            _json_response(self, HTTPStatus.OK, payload)
            return

        if path == "/api/v1/latest/daily-brief":
            payload = self.server.fetch_latest("daily_brief")
            _json_response(self, HTTPStatus.OK, payload)
            return

        if path == "/api/v1/latest/board-report":
            payload = self.server.fetch_latest("board_report")
            _json_response(self, HTTPStatus.OK, payload)
            return

        if path == "/api/v1/latest/hourly-plan":
            payload = self.server.fetch_latest("hourly_plan")
            _json_response(self, HTTPStatus.OK, payload)
            return
        if path == "/api/v1/latest/triage-report":
            payload = self.server.fetch_latest("triage_report")
            _json_response(self, HTTPStatus.OK, payload)
            return

        if path == "/api/v1/alerts":
            limit = int(query.get("limit", ["20"])[0])
            severity = query.get("severity", [""])[0] or None
            category = query.get("category", [""])[0] or None
            payload = {"alerts": self.server.fetch_alerts(limit, severity, category)}
            _json_response(self, HTTPStatus.OK, payload)
            return
        if path == "/api/v1/tasks":
            limit = int(query.get("limit", ["20"])[0])
            status = query.get("status", ["needsAction"])[0] or None
            list_id = query.get("list_id", [""])[0] or None
            search = query.get("search", [""])[0] or None
            with _LOCK:
                conn = self.server._connect()
                try:
                    init_db(conn)
                    rows = list_tasks(
                        conn,
                        list_id=list_id,
                        status=status,
                        search=search,
                        limit=limit,
                    )
                finally:
                    conn.close()
            payload = {"tasks": rows}
            _json_response(self, HTTPStatus.OK, payload)
            return

        _json_response(self, HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:
        if not self._check_auth():
            _json_response(self, HTTPStatus.UNAUTHORIZED, {"error": "Unauthorized"})
            return
        if self.path != "/api/v1/ack":
            _json_response(self, HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        data = _read_json(self)
        item_type = data.get("item_type")
        item_id = data.get("item_id")
        note = data.get("note", "")
        if not item_type or item_id is None:
            _json_response(self, HTTPStatus.BAD_REQUEST, {"error": "item_type and item_id required"})
            return
        ack_id = self.server.insert_ack(item_type, str(item_id), note)
        _json_response(self, HTTPStatus.OK, {"ack_id": ack_id})

    def log_message(self, format: str, *args: Any) -> None:
        return


class AtlasServer(ThreadingHTTPServer):
    def __init__(self, host: str, port: int, db_path: Path, token: str, allow_lan_cors: bool):
        self.config = ServerConfig(
            db_path=db_path, token=token, host=host, port=port, allow_lan_cors=allow_lan_cors
        )
        super().__init__((host, port), AtlasRequestHandler)

    def now_iso(self) -> str:
        return datetime.utcnow().isoformat() + "Z"

    def _connect(self):
        return connect(self.config.db_path)

    def fetch_latest(self, kind: str) -> dict:
        with _LOCK:
            conn = self._connect()
            try:
                try:
                    if kind == "daily_brief":
                        row = get_latest_daily_brief(conn)
                    elif kind == "board_report":
                        row = get_latest_board_report(conn)
                    elif kind == "hourly_plan":
                        row = get_latest_hourly_plan(conn)
                    elif kind == "triage_report":
                        row = get_latest_triage_report(conn)
                    else:
                        row = None
                except sqlite3.Error:
                    row = None
            finally:
                conn.close()
        return {"data": row}

    def fetch_alerts(self, limit: int, severity: str | None, category: str | None) -> list[dict]:
        with _LOCK:
            conn = self._connect()
            try:
                try:
                    return list_alerts(conn, severity=severity, category=category, limit=limit)
                except sqlite3.Error:
                    return []
            finally:
                conn.close()

    def insert_ack(self, item_type: str, item_id: str, note: str) -> int:
        with _LOCK:
            conn = self._connect()
            try:
                init_db(conn)
                return insert_acknowledgement(conn, item_type, item_id, note)
            finally:
                conn.close()


def create_server(
    host: str,
    port: int,
    db_path: Path | None,
    token: str,
    allow_lan_cors: bool = False,
) -> AtlasServer:
    resolved_path = (db_path or default_db_path()).expanduser().resolve()
    return AtlasServer(host, port, resolved_path, token, allow_lan_cors)


def run_server(host: str, port: int, db_path: Path | None, allow_lan_cors: bool = False) -> None:
    token = os.environ.get("ATLAS_MOBILE_TOKEN")
    if not token:
        raise RuntimeError("ATLAS_MOBILE_TOKEN must be set.")
    server = create_server(host, port, db_path, token, allow_lan_cors)
    server.serve_forever()
