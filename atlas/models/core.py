from datetime import time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WorkingHours(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: time
    end: time

    @model_validator(mode="after")
    def validate_range(self) -> "WorkingHours":
        if self.end <= self.start:
            raise ValueError("working_hours.end must be after working_hours.start")
        return self


class AtlasConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    timezone: str
    working_hours: WorkingHours = Field(alias="working_hours")
    goals: list[str]

    @field_validator("timezone")
    @classmethod
    def timezone_required(cls, value: str) -> str:
        if not value:
            raise ValueError("timezone must be non-empty")
        return value

    @field_validator("goals")
    @classmethod
    def goals_required(cls, value: list[str]) -> list[str]:
        if len(value) != 3:
            raise ValueError("goals must contain exactly 3 items")
        if any(not goal.strip() for goal in value):
            raise ValueError("goals must be non-empty strings")
        return value
