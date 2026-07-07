from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Verdict = Literal["LOW", "MEDIUM", "HIGH"]

# Words in a MiroFish audience report that signal negative/backlash reaction.
BACKLASH_KEYWORDS = (
    "backlash",
    "outrage",
    "controversy",
    "criticism",
    "boycott",
    "protest",
    "anger",
    "negative",
    "concern",
    "distrust",
    "polariz",
)


class SeedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    filename: str
    content: str


class PredictionSeed(BaseModel):
    """A message/announcement/brief plus the audience-reaction question to rehearse."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    requirement: str
    documents: list[SeedDocument] = Field(default_factory=list)
    project_name: str | None = None
    additional_context: str | None = None


class PredictionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    report_markdown: str
    outline: str = ""
    verdict: Verdict
    risk_score: float = Field(ge=0.0, le=1.0)
    trajectories: list[str] = Field(default_factory=list)
    simulation_id: str | None = None
    report_id: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


def derive_verdict(report_markdown: str) -> tuple[Verdict, float]:
    """Approximate an audience-reaction risk from report text.

    Heuristic only; a MiroFish report is prose. Swap for an LLM-based
    classification (Atlas already has an OpenAI client) when higher fidelity
    is needed.
    """
    text = report_markdown.lower()
    hits = sum(text.count(keyword) for keyword in BACKLASH_KEYWORDS)
    if hits >= 6:
        return "HIGH", min(1.0, 0.7 + 0.03 * (hits - 6))
    if hits >= 2:
        return "MEDIUM", 0.3 + 0.05 * (hits - 2)
    return "LOW", 0.1
