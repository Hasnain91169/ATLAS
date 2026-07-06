from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class CalendarEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str
    start: datetime
    end: datetime
    kind: str = "meeting"

    @field_validator("title")
    @classmethod
    def title_required(cls, value: str) -> str:
        if not value:
            raise ValueError("title must be non-empty")
        return value

    @model_validator(mode="after")
    def validate_range(self) -> "CalendarEvent":
        if self.end <= self.start:
            raise ValueError("event.end must be after event.start")
        return self
