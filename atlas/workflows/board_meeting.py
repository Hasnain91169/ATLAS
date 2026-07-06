from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from atlas.models.core import AtlasConfig
from atlas.models.reports import (
    AtlasExecutiveSummary,
    BoardReport,
    DecisionsReport,
    DepartmentReport,
    PostMortemReport,
    RiskReport,
)
from atlas.risk.alerts import AlertDraft
from atlas.risk.rules import RiskSignals, evaluate_risks, should_veto
from atlas.storage.sqlite import connect, default_db_path, init_db
from atlas.utils.time import resolve_timezone, today_in_timezone
from atlas.agents.context import build_agent_context
from atlas.agents.run import run_agents

MAX_LIST_ITEMS = 3
_BULLET_RE = re.compile(r"^(\d+[\.\)]|[-*+])\s+")


def _limit(items: list[str], max_items: int = MAX_LIST_ITEMS) -> list[str]:
    return items[:max_items]


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _build_executive_summary(config: AtlasConfig) -> AtlasExecutiveSummary:
    return AtlasExecutiveSummary(
        last_week_objective=config.goals[0],
        execution_score=78,
        capacity_used="82%",
        key_constraints=["Calendar load", "Energy management"],
    )


def _build_department_reports(config: AtlasConfig) -> list[DepartmentReport]:
    return [
        DepartmentReport(
            department="Strategy",
            summary="Recalibrated long-range priorities around current goals.",
            wins=_limit([f"Clarified trajectory for: {config.goals[0]}"]),
            concerns=_limit(["Need deeper opportunity cost review."]),
            asks=_limit(["Schedule 45m strategy review."]),
        ),
        DepartmentReport(
            department="Operations",
            summary="Execution rhythm stabilized with consistent daily briefs.",
            wins=_limit(["Improved planning cadence."]),
            concerns=_limit(["Meeting load compresses focus time."]),
            asks=_limit(["Block two focus windows next week."]),
        ),
        DepartmentReport(
            department="Health",
            summary="Energy levels stable but recovery margin is thin.",
            wins=_limit(["Hit training targets twice."]),
            concerns=_limit(["Sleep debt risk if meetings extend."]),
            asks=_limit(["Protect bedtime routine."]),
        ),
        DepartmentReport(
            department="Faith",
            summary="Prayer windows respected but need firmer boundaries.",
            wins=_limit(["Morning alignment check completed."]),
            concerns=_limit(["Evening window slipped once."]),
            asks=_limit(["Add 10m buffer before evening block."]),
        ),
        DepartmentReport(
            department="Relationships",
            summary="Family touchpoints maintained; social debt monitored.",
            wins=_limit(["Completed two key check-ins."]),
            concerns=_limit(["One follow-up delayed."]),
            asks=_limit(["Schedule one relationship block."]),
        ),
        DepartmentReport(
            department="Wealth",
            summary="Spending discipline intact; risk exposure unchanged.",
            wins=_limit(["Tracked discretionary spend."]),
            concerns=_limit(["Investment review overdue."]),
            asks=_limit(["Set a 30m finance review."]),
        ),
    ]


def _assess_risk(
    alerts_count: int, veto_override: bool | None, veto: bool
) -> RiskReport:
    rationale = "Risk veto active due to triggered alerts." if veto else "No veto."
    issues = [f"{alerts_count} drafted alert(s) generated"] if alerts_count else []
    if veto_override is not None:
        rationale = "Risk veto forced via override."
    return RiskReport(veto=veto, issues=_limit(issues), rationale=rationale)


def _build_post_mortem() -> PostMortemReport:
    return PostMortemReport(
        failures=_limit(["Overfilled calendar reduced focus blocks."]),
        lessons=_limit(["Protect deep work before adding meetings."]),
        fixes=_limit(["Add a hard cap on meeting hours."]),
    )


def _build_decisions(config: AtlasConfig, veto: bool) -> DecisionsReport:
    downgrade_note = None
    primary = config.goals[0]
    optional = _limit(config.goals[1:])
    dropped: list[str] = []
    if veto:
        downgrade_note = "Objective downgraded due to risk veto."
        dropped = _limit(optional)
        optional = []
    return DecisionsReport(
        primary_objective=primary,
        optional_objectives=optional,
        dropped_items=dropped,
        downgrade_note=downgrade_note,
    )


def _render_markdown(
    week_start: date,
    summary: AtlasExecutiveSummary,
    reports: list[DepartmentReport],
    risk: RiskReport,
    alerts: list[AlertDraft],
    agent_drafts: dict[str, str],
    post_mortem: PostMortemReport,
    decisions: DecisionsReport,
) -> str:
    lines: list[str] = []
    lines.append(f"# Weekly Board Meeting - Week of {week_start.isoformat()}")
    lines.append("")
    lines.append("## Atlas Executive Summary")
    lines.append(f"- Last Week Objective: {summary.last_week_objective}")
    lines.append(f"- Execution Score: {summary.execution_score}")
    lines.append(f"- Capacity Used: {summary.capacity_used}")
    lines.append("- Key Constraints:")
    for item in _limit(summary.key_constraints):
        lines.append(f"  - {item}")
    lines.append("")
    lines.append("## Department Reports")
    for report in reports:
        lines.append(f"### {report.department}")
        lines.append(f"- Summary: {report.summary}")
        lines.append("- Wins:")
        for item in _limit(report.wins):
            lines.append(f"  - {item}")
        lines.append("- Concerns:")
        for item in _limit(report.concerns):
            lines.append(f"  - {item}")
        lines.append("- Asks:")
        for item in _limit(report.asks):
            lines.append(f"  - {item}")
    lines.append("")
    lines.append("## Risk & Compliance Interruption")
    lines.append(f"- Veto: {'YES' if risk.veto else 'NO'}")
    lines.append(f"- Rationale: {risk.rationale}")
    lines.append("- Issues:")
    if risk.issues:
        for item in _limit(risk.issues):
            lines.append(f"  - {item}")
    else:
        lines.append("  - None")
    lines.append("- Draft Alerts:")
    if alerts:
        for alert in alerts:
            lines.append(f"  - {alert.title} ({alert.severity})")
            for line in alert.message_markdown.splitlines():
                lines.append(f"    {line}")
    else:
        lines.append("  - None")
    lines.append("")
    lines.append("## Department Head Drafts (AI)")
    for name, draft in agent_drafts.items():
        lines.append(f"### {name}")
        for line in draft.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if _BULLET_RE.match(stripped):
                lines.append(stripped)
            else:
                lines.append(f"- {stripped}")
    lines.append("")
    lines.append("## Post-Mortem & Learning")
    lines.append("- Failures:")
    for item in _limit(post_mortem.failures):
        lines.append(f"  - {item}")
    lines.append("- Lessons:")
    for item in _limit(post_mortem.lessons):
        lines.append(f"  - {item}")
    lines.append("- Fixes:")
    for item in _limit(post_mortem.fixes):
        lines.append(f"  - {item}")
    lines.append("")
    lines.append("## Decisions for Next Week")
    lines.append(f"- Primary Objective: {decisions.primary_objective}")
    if decisions.optional_objectives:
        lines.append("- Optional Objectives:")
        for item in _limit(decisions.optional_objectives):
            lines.append(f"  - {item}")
    if decisions.dropped_items:
        lines.append("- Explicitly Dropped:")
        for item in _limit(decisions.dropped_items):
            lines.append(f"  - {item}")
    if decisions.downgrade_note:
        lines.append(f"- {decisions.downgrade_note}")
    lines.append("")
    return "\n".join(lines)


def _derive_tags(risk: RiskReport) -> list[str]:
    tags = ["board-meeting"]
    if risk.veto:
        tags.append("risk-veto")
    return tags


def generate_board_report(
    config: AtlasConfig,
    veto_override: bool | None = None,
    risk_signals: RiskSignals | None = None,
    now: datetime | None = None,
    enable_llm: bool = False,
    db_path: str | Path | None = None,
) -> BoardReport:
    tz = resolve_timezone(config.timezone)
    if now is None:
        day = today_in_timezone(tz)
        local_now = datetime.now(timezone.utc).astimezone(tz)
    else:
        local_now = now.astimezone(tz)
        day = local_now.date()
    week_start = _week_start(day)
    summary = _build_executive_summary(config)
    reports = _build_department_reports(config)
    signals = risk_signals or RiskSignals()
    alerts = evaluate_risks(signals)
    veto = veto_override if veto_override is not None else should_veto(alerts)
    risk = _assess_risk(len(alerts), veto_override, veto)
    post_mortem = _build_post_mortem()
    decisions = _build_decisions(config, veto)
    if enable_llm:
        resolved_db_path = (
            Path(db_path).expanduser().resolve() if db_path else default_db_path()
        )
        conn = connect(resolved_db_path)
        try:
            init_db(conn)
            context = build_agent_context(conn)
        finally:
            conn.close()
        agent_drafts = run_agents(context, enable_llm=True, fail_open=True)
    else:
        alerts_summary = f"{len(alerts)} draft alerts"
        context = {
            "daily_brief_markdown": "No daily brief available.",
            "tasks_summary": "No synced tasks available.",
            "alerts_summary": alerts_summary,
        }
        agent_drafts = run_agents(context, enable_llm=False)
    markdown = _render_markdown(
        week_start, summary, reports, risk, alerts, agent_drafts, post_mortem, decisions
    )
    payload = {
        "executive_summary": summary.model_dump(),
        "department_reports": [report.model_dump() for report in reports],
        "risk": risk.model_dump(),
        "risk_alerts": [alert.model_dump() for alert in alerts],
        "risk_signals": asdict(signals),
        "post_mortem": post_mortem.model_dump(),
        "decisions": decisions.model_dump(),
        "agent_drafts": agent_drafts,
    }
    tags = _derive_tags(risk)
    return BoardReport(
        created_at=local_now.astimezone(timezone.utc),
        week_start_date=week_start,
        markdown=markdown,
        payload=payload,
        tags=tags,
        alerts=alerts,
    )


def board_report_payload_json(report: BoardReport) -> str:
    return json.dumps(report.payload, sort_keys=True)
