from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WorkerTask(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str
    title: str
    instructions: str
    inputs: dict
    expected_output: str


class WorkerLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    summary: str
    findings: list[str]
    risks: list[str]
    recommendations: list[str]
    proposed_actions: list[dict]
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainties: list[str]
    missing_inputs: list[str]


class WorkerResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    task_id: str
    output: str
    llm_output: WorkerLLMOutput | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    assumptions: list[str]
    uncertainties: list[str] = Field(default_factory=list)
    missing_inputs: list[str]


class HeadReport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    head_name: str
    domain_summary: str
    key_risks: list[str]
    recommendations_for_atlas: list[str]
    proposed_actions: list[dict]
    worker_trace: list[dict]
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainties: list[str]


class HeadSynthesis(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    domain_summary: str
    key_risks: list[str]
    recommendations_for_atlas: list[str]
    proposed_actions: list[dict]
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainties: list[str]
