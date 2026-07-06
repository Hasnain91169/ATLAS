from __future__ import annotations

from atlas.actions.models import RequestMoreInfoAction, TaskCompleteAction, parse_action
from atlas.tasks.base import TasksAdapter


def execute_action(action_type: str, payload: dict, tasks_adapter: TasksAdapter) -> None:
    action = parse_action(action_type, payload)
    if isinstance(action, TaskCompleteAction):
        tasks_adapter.complete_task(action.list_id, action.task_id)
        return
    if isinstance(action, RequestMoreInfoAction):
        raise ValueError("request_more_info is draft-only")
    raise ValueError(f"Unsupported action type: {action_type}")
