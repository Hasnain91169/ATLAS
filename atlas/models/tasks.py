from pydantic import BaseModel, ConfigDict, Field


class TaskList(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str
    title: str


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str
    title: str
    status: str
    notes: str | None = None
    due: str | None = None
    updated: str | None = None
    parent: str | None = None
    position: str | None = None
    completed: str | None = None
    list_id: str | None = Field(default=None, exclude=True)
