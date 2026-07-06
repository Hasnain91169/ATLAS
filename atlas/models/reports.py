from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.risk.alerts import AlertDraft


class AtlasExecutiveSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    last_week_objective: str
    execution_score: int = Field(ge=0, le=100)
    capacity_used: str
    key_constraints: list[str]


class DepartmentReport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    department: str
    summary: str
    wins: list[str]
    concerns: list[str]
    asks: list[str]


class RiskReport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    veto: bool
    issues: list[str]
    rationale: str


class PostMortemReport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    failures: list[str]
    lessons: list[str]
    fixes: list[str]


class DecisionsReport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    primary_objective: str
    optional_objectives: list[str]
    dropped_items: list[str]
    downgrade_note: str | None = None


class BoardReport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    created_at: datetime
    week_start_date: date
    markdown: str
    payload: dict
    tags: list[str]
    alerts: list[AlertDraft]
