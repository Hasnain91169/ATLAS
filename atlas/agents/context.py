from __future__ import annotations

from typing import Any

from atlas.storage.sqlite import get_latest_daily_brief, list_alerts, list_tasks


def build_agent_context(conn) -> dict[str, Any]:
    daily_brief = get_latest_daily_brief(conn)
    if daily_brief and daily_brief.get("markdown"):
        daily_brief_markdown = daily_brief["markdown"]
    else:
        daily_brief_markdown = "No daily brief available."

    task_rows = list_tasks(conn, status="needsAction", limit=5)
    if task_rows:
        task_lines = ["Top needsAction tasks:"]
        for task in task_rows:
            due = task["due"] or "No due date"
            list_id = task.get("list_id")
            list_hint = f", list_id: {list_id}" if list_id else ""
            task_lines.append(f"- {task['title']} (due: {due}{list_hint})")
        tasks_summary = "\n".join(task_lines)
    else:
        tasks_summary = "No synced tasks available."

    alert_rows = list_alerts(conn, limit=10)
    if alert_rows:
        alert_lines = ["Recent draft alerts:"]
        for alert in alert_rows:
            alert_lines.append(f"- [{alert['severity']}] {alert['title']}")
        alerts_summary = "\n".join(alert_lines)
    else:
        alerts_summary = "No draft alerts available."

    return {
        "daily_brief_markdown": daily_brief_markdown,
        "tasks_summary": tasks_summary,
        "alerts_summary": alerts_summary,
    }
