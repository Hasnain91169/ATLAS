from __future__ import annotations

from typing import Any

from atlas.agents.context import build_agent_context
from atlas.llm.base import LLMClient, build_llm_from_env
from atlas.llm.openai import OpenAIClient
from atlas.org.protocol import HeadReport
from atlas.org.roles import FinanceHead, LearningHead, OperationsHead, RiskComplianceHead
from atlas.org.trace import Tracer
from atlas.storage.sqlite import list_alerts, list_tasks


def build_context(conn) -> dict[str, Any]:
    summary = build_agent_context(conn)
    task_rows = list_tasks(conn, status="needsAction", limit=10)
    tasks = [
        {
            "id": row["id"],
            "title": row["title"],
            "due": row["due"],
            "updated": row["updated"],
            "status": row["status"],
            "list_id": row["list_id"],
        }
        for row in task_rows
    ]
    alerts = list_alerts(conn, limit=10)
    return {
        **summary,
        "tasks": tasks,
        "alerts": alerts,
    }


def run_department_heads(
    context: dict[str, Any],
    enable_llm: bool,
    llm: LLMClient | None = None,
    tracer: Tracer | None = None,
) -> list[HeadReport]:
    heads = [OperationsHead(), RiskComplianceHead(), FinanceHead(), LearningHead()]
    if enable_llm and llm is None:
        llm = build_llm_from_env() or OpenAIClient.from_env()
    reports: list[HeadReport] = []
    for head in heads:
        report = head.run(context, enable_llm, llm, tracer)
        reports.append(report)
    return reports


def run_atlas_synthesis(
    context: dict[str, Any], head_reports: list[HeadReport]
) -> dict[str, Any]:
    ordered_reports = _order_reports_by_domain(head_reports)
    what_mattered = [
        f"{report.head_name}: {report.domain_summary}" for report in ordered_reports
    ]
    what_happens_next: list[str] = []
    for report in ordered_reports:
        what_happens_next.extend(report.recommendations_for_atlas)

    approval_candidates: list[dict[str, Any]] = []
    for report in ordered_reports:
        for action in report.proposed_actions:
            action_type = action.get("action_type")
            payload = action.get("payload")
            if not action_type or not isinstance(payload, dict):
                continue
            approval_candidates.append(
                {
                    "action_type": action_type,
                    "payload": payload,
                    "reason": action.get("reason", "No reason provided."),
                    "source_head": report.head_name,
                }
            )
    approval_candidates = _order_candidates_by_domain(approval_candidates)[:5]

    return {
        "what_mattered": what_mattered,
        "what_happens_next": what_happens_next,
        "approval_candidates": approval_candidates,
    }


def _domain_for_head(head_name: str) -> str:
    mapping = {
        "Risk & Compliance": "Health",
        "Finance": "Wealth",
        "Operations": "Wealth",
        "Learning": "Wealth",
    }
    return mapping.get(head_name, "Wealth")


def _domain_rank(domain: str) -> int:
    order = ["Religion", "Health", "Relationships", "Wealth"]
    try:
        return order.index(domain)
    except ValueError:
        return len(order)


def _order_reports_by_domain(reports: list[HeadReport]) -> list[HeadReport]:
    return sorted(reports, key=lambda report: _domain_rank(_domain_for_head(report.head_name)))


def _order_candidates_by_domain(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda candidate: _domain_rank(_domain_for_head(candidate.get("source_head", ""))),
    )
