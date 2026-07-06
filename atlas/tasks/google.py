from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from atlas.models.tasks import Task, TaskList
from atlas.tasks.base import TasksAdapter

TOKEN_URL = "https://oauth2.googleapis.com/token"
TASKLISTS_URL = "https://tasks.googleapis.com/tasks/v1/users/@me/lists"
TASKS_URL_TEMPLATE = "https://tasks.googleapis.com/tasks/v1/lists/{list_id}/tasks"
TASK_URL_TEMPLATE = "https://tasks.googleapis.com/tasks/v1/lists/{list_id}/tasks/{task_id}"


class GoogleTasksAdapter(TasksAdapter):
    def __init__(
        self, client_id: str, client_secret: str, refresh_token: str, scope: str
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._scope = scope
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    @classmethod
    def from_env(cls) -> "GoogleTasksAdapter":
        client_id = os.environ.get("GOOGLE_TASKS_CLIENT_ID")
        client_secret = os.environ.get("GOOGLE_TASKS_CLIENT_SECRET")
        refresh_token = os.environ.get("GOOGLE_TASKS_REFRESH_TOKEN")
        scope = os.environ.get("GOOGLE_TASKS_SCOPE", "readonly")
        if not client_id or not client_secret or not refresh_token:
            raise RuntimeError(
                "GOOGLE_TASKS_CLIENT_ID/SECRET/REFRESH_TOKEN must be set."
            )
        return cls(client_id, client_secret, refresh_token, scope)

    def _refresh_access_token(self) -> str:
        data = urlencode(
            {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        req = Request(TOKEN_URL, data=data, method="POST")
        with urlopen(req, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 3600))
        self._access_token = token
        self._expires_at = time.time() + max(0, expires_in - 30)
        return token

    def _get_access_token(self) -> str:
        if not self._access_token or time.time() >= self._expires_at:
            return self._refresh_access_token()
        return self._access_token

    def _request_json(
        self,
        url: str,
        params: dict[str, str] | None = None,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if params:
            url = f"{url}?{urlencode(params)}"
        token = self._get_access_token()
        data = None
        headers = {"Authorization": f"Bearer {token}"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = Request(url, data=data, headers=headers, method=method)
        with urlopen(req, timeout=10) as response:
            body = response.read()
        if not body:
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            snippet = body.decode("utf-8", errors="replace")[:200]
            raise RuntimeError(f"Non-JSON response: {snippet}") from exc

    def _has_write_scope(self) -> bool:
        scope = self._scope.lower()
        if scope == "readonly" or "tasks.readonly" in scope:
            return False
        return True

    def list_task_lists(self) -> list[TaskList]:
        lists: list[TaskList] = []
        page_token: str | None = None
        while True:
            params = {"maxResults": "100"}
            if page_token:
                params["pageToken"] = page_token
            payload = self._request_json(TASKLISTS_URL, params=params)
            for item in payload.get("items", []):
                lists.append(TaskList(id=item["id"], title=item.get("title", "")))
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
        return lists

    def list_tasks(self, list_id: str) -> list[Task]:
        tasks: list[Task] = []
        page_token: str | None = None
        while True:
            params = {
                "maxResults": "100",
                "showCompleted": "true",
                "showHidden": "true",
            }
            if page_token:
                params["pageToken"] = page_token
            payload = self._request_json(
                TASKS_URL_TEMPLATE.format(list_id=list_id), params=params
            )
            for item in payload.get("items", []):
                tasks.append(
                    Task(
                        id=item["id"],
                        title=item.get("title", ""),
                        status=item.get("status", "needsAction"),
                        notes=item.get("notes"),
                        due=item.get("due"),
                        updated=item.get("updated"),
                        parent=item.get("parent"),
                        position=item.get("position"),
                        completed=item.get("completed"),
                        list_id=list_id,
                    )
                )
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
        return tasks

    def complete_task(self, list_id: str, task_id: str) -> None:
        if not self._has_write_scope():
            raise RuntimeError(
                "GOOGLE_TASKS_SCOPE is read-only; set it to "
                "'https://www.googleapis.com/auth/tasks' and refresh the token."
            )
        url = TASK_URL_TEMPLATE.format(list_id=list_id, task_id=task_id)
        self._request_json(url, method="PATCH", payload={"status": "completed"})
