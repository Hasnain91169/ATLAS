from datetime import datetime, timezone

from atlas.models.tasks import Task, TaskList
from atlas.tasks.base import TasksAdapter


class StubTasksAdapter(TasksAdapter):
    def __init__(self) -> None:
        self.completed: list[tuple[str, str]] = []

    def list_task_lists(self) -> list[TaskList]:
        return [TaskList(id="stub-list", title="Stub List")]

    def list_tasks(self, list_id: str) -> list[Task]:
        now = datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc).isoformat()
        return [
            Task(
                id="task-1",
                title="Draft weekly summary",
                status="needsAction",
                due="2025-01-02T12:00:00Z",
                updated=now,
                list_id=list_id,
            ),
            Task(
                id="task-2",
                title="Review budget notes",
                status="needsAction",
                updated=now,
                list_id=list_id,
            ),
        ]

    def complete_task(self, list_id: str, task_id: str) -> None:
        self.completed.append((list_id, task_id))
