from __future__ import annotations

import json
from typing import Any

from atlas.llm.base import LLMClient
from atlas.org.protocol import HeadReport
from atlas.org.trace import Tracer, maybe_span

# Read-only tools a head agent can call to gather what it needs from context.
AGENT_TOOLS = ("query_tasks", "query_alerts", "read_brief")

HEAD_ROLES = {
    "Operations": "operations, scheduling, and task execution",
    "Risk & Compliance": "risk, compliance, and health guardrails",
    "Finance": "finance, budget, and spending obligations",
    "Learning": "recurring lessons and process improvements",
}

# One structured decision per step: either call a tool, or finish with a report.
DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["use_tool", "final"]},
        "tool": {"type": "string", "enum": list(AGENT_TOOLS)},
        "thought": {"type": "string"},
        "domain_summary": {"type": "string"},
        "key_risks": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["action"],
    "additionalProperties": False,
}


def run_department_heads_agent(
    context: dict[str, Any],
    llm: LLMClient,
    *,
    max_steps: int = 4,
    tracer: Tracer | None = None,
) -> list[HeadReport]:
    """Run each department head as a bounded tool-use agent."""
    reports: list[HeadReport] = []
    for name, role in HEAD_ROLES.items():
        with maybe_span(tracer, name, "head"):
            reports.append(
                run_head_agent(name, role, context, llm, max_steps=max_steps, tracer=tracer)
            )
    return reports


def run_head_agent(
    head_name: str,
    role: str,
    context: dict[str, Any],
    llm: LLMClient,
    *,
    max_steps: int = 4,
    tracer: Tracer | None = None,
) -> HeadReport:
    transcript: list[dict[str, Any]] = []
    calls = 0

    for step in range(max_steps):
        decision = _decide(llm, head_name, role, transcript, force_final=False, tracer=tracer, step=step)
        calls += 1
        if str(decision.get("action")) == "final":
            return _to_report(head_name, decision, transcript, calls)
        tool = str(decision.get("tool") or "")
        transcript.append(
            {"tool": tool, "observation": _run_tool(tool, context)}
        )

    # Tool budget exhausted — force a final synthesis from what was gathered.
    decision = _decide(
        llm, head_name, role, transcript, force_final=True, tracer=tracer, step=max_steps
    )
    return _to_report(head_name, decision, transcript, calls + 1)


def _run_tool(tool: str, context: dict[str, Any]) -> Any:
    if tool == "query_tasks":
        return context.get("tasks", [])
    if tool == "query_alerts":
        return context.get("alerts", [])
    if tool == "read_brief":
        return context.get("daily_brief_markdown", "")
    return f"unknown tool: {tool!r}"


def _decide(
    llm: LLMClient,
    head_name: str,
    role: str,
    transcript: list[dict[str, Any]],
    *,
    force_final: bool,
    tracer: Tracer | None,
    step: int,
) -> dict[str, Any]:
    prompt = _build_prompt(head_name, role, transcript, force_final)
    with maybe_span(tracer, f"{head_name}-step{step + 1}", "agent_step", head_name) as span:
        try:
            decision = llm.complete_structured(prompt, DECISION_SCHEMA)
        except Exception:
            decision = {"action": "final", "domain_summary": f"{head_name} agent failed to respond."}
        if span is not None:
            span.usage = getattr(llm, "last_usage", None)
    if not isinstance(decision, dict):
        return {"action": "final", "domain_summary": f"{head_name} agent returned no decision."}
    return decision


def _build_prompt(
    head_name: str, role: str, transcript: list[dict[str, Any]], force_final: bool
) -> str:
    tools = ", ".join(AGENT_TOOLS)
    system = (
        f"You are the {head_name} department head, responsible for {role}. "
        f"You have read-only tools: {tools}. Call one tool at a time to gather the "
        "context you need, then finish. When you have enough, set action='final' and "
        "fill domain_summary, key_risks, and recommendations. Keep it concise."
    )
    observed = (
        json.dumps(transcript, ensure_ascii=True, indent=2)
        if transcript
        else "(no tools called yet)"
    )
    instruction = (
        "You have gathered enough — you MUST set action='final' now."
        if force_final
        else "Decide the single next step (use_tool or final)."
    )
    return (
        f"SYSTEM:\n{system}\n\n"
        f"USER:\nObservations so far:\n{observed}\n\n{instruction}\n"
        "Return JSON only matching the schema."
    )


def _to_report(
    head_name: str, decision: dict[str, Any], transcript: list[dict[str, Any]], calls: int
) -> HeadReport:
    tools_used = [entry["tool"] for entry in transcript]
    return HeadReport(
        head_name=head_name,
        domain_summary=str(decision.get("domain_summary") or f"{head_name} agent completed."),
        key_risks=[str(r) for r in (decision.get("key_risks") or [])][:3],
        recommendations_for_atlas=[str(r) for r in (decision.get("recommendations") or [])][:5],
        # The agent path analyzes and advises; it does not emit executable actions.
        proposed_actions=[],
        worker_trace=[{"mode": "agent", "llm_calls": calls, "tools_used": tools_used}],
        confidence=0.6,
        uncertainties=[],
    )
