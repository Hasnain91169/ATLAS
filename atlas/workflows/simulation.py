from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from atlas.brief.generator import generate_daily_brief
from atlas.calendar.stub import StubCalendarAdapter
from atlas.models.core import AtlasConfig
from atlas.storage.sqlite import (
    connect,
    default_db_path,
    init_db,
    insert_alerts,
    insert_board_report,
    insert_daily_brief,
    insert_hourly_plan,
    insert_triage_report,
)
from atlas.utils.time import resolve_timezone
from atlas.workflows.board_meeting import board_report_payload_json, generate_board_report
from atlas.workflows.email_triage import generate_triage_report, load_messages, triage_payload_json
from atlas.workflows.hourly_planner import generate_hourly_plan, hourly_plan_payload_json


DEFAULT_MESSAGES_PATH = Path(__file__).resolve().parents[2] / "examples" / "messages.yaml"


@dataclass(frozen=True)
class SimulationSummary:
    counts: dict[str, int]
    latest: dict[str, str | None]


def _summarize(conn) -> SimulationSummary:
    tables = {
        "daily_brief": "timestamp",
        "hourly_plan": "created_at",
        "board_report": "created_at",
        "triage_report": "created_at",
        "alerts": "created_at",
        "acknowledgements": "created_at",
    }
    counts: dict[str, int] = {}
    latest: dict[str, str | None] = {}
    for table, column in tables.items():
        row = conn.execute(
            f"SELECT COUNT(*) AS count, MAX({column}) AS latest FROM {table}"
        ).fetchone()
        counts[table] = int(row["count"])
        latest[table] = row["latest"]
    return SimulationSummary(counts=counts, latest=latest)


def _verify(summary: SimulationSummary, days: int) -> None:
    errors = []
    if summary.counts["daily_brief"] < days:
        errors.append("daily_brief count below expected days")
    if summary.counts["hourly_plan"] < days:
        errors.append("hourly_plan count below expected days")
    if summary.counts["board_report"] < 1:
        errors.append("board_report missing")
    if summary.counts["triage_report"] < 1:
        errors.append("triage_report missing")
    if errors:
        raise RuntimeError("; ".join(errors))


def simulate_week(
    config: AtlasConfig,
    db_path: Path | None,
    start_day: date,
    days: int = 7,
    messages_path: Path | None = None,
) -> dict[str, dict[str, str | int | None]]:
    tz = resolve_timezone(config.timezone)
    adapter = StubCalendarAdapter()
    resolved_db_path = (db_path or default_db_path()).expanduser().resolve()
    board_generated = False

    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        for offset in range(days):
            day = start_day + timedelta(days=offset)
            events = adapter.fetch_events(day, tz)
            brief = generate_daily_brief(config, events, day, tz)
            plan = generate_hourly_plan(config, events, day, tz)

            brief_id = insert_daily_brief(
                conn, day.isoformat(), brief.markdown, brief.tags
            )
            if brief.alerts:
                insert_alerts(conn, "daily_brief", brief_id, brief.alerts)

            plan_id = insert_hourly_plan(
                conn,
                day.isoformat(),
                plan.markdown,
                hourly_plan_payload_json(plan),
                plan.tags,
            )
            if plan.alerts:
                insert_alerts(conn, "hourly_plan", plan_id, plan.alerts)

            if not board_generated and (day.weekday() == 0 or offset == 0):
                now = datetime.combine(day, time(9, 0), tzinfo=tz).astimezone(
                    timezone.utc
                )
                report = generate_board_report(config, now=now)
                report_id = insert_board_report(
                    conn,
                    report.week_start_date.isoformat(),
                    report.markdown,
                    board_report_payload_json(report),
                    report.tags,
                )
                if report.alerts:
                    insert_alerts(conn, "board_meeting", report_id, report.alerts)
                board_generated = True

        triage_messages = load_messages(messages_path or DEFAULT_MESSAGES_PATH)
        triage_report = generate_triage_report(triage_messages)
        triage_id = insert_triage_report(
            conn,
            triage_report.markdown,
            triage_payload_json(triage_report),
            triage_report.tags,
        )
        if triage_report.alerts:
            insert_alerts(conn, "triage_report", triage_id, triage_report.alerts)

        summary = _summarize(conn)
        _verify(summary, days)
    finally:
        conn.close()

    return {
        table: {"count": summary.counts[table], "latest": summary.latest[table]}
        for table in summary.counts
    }
