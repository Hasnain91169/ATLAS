from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskCompleteAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    list_id: str
    task_id: str
    note: str | None = None


class RequestMoreInfoAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str
    needed_fields: list[str] = Field(default_factory=list)
    context_hint: str | None = None


def parse_action(action_type: str, payload_dict: dict[str, Any]) -> BaseModel:
    if action_type == "task_complete":
        return TaskCompleteAction.model_validate(payload_dict)
    if action_type == "request_more_info":
        return RequestMoreInfoAction.model_validate(payload_dict)
    raise ValueError(f"Unknown action_type: {action_type}")
