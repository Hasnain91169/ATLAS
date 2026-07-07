import argparse
import ipaddress
import json
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from atlas.actions.executor import execute_action
from atlas.actions.models import parse_action
from atlas.agents.context import build_agent_context
from atlas.agents.run import run_agents
from atlas.brief.generator import generate_daily_brief
from atlas.calendar.stub import StubCalendarAdapter
from atlas.config import load_config
from atlas.mobile.server import create_server
from atlas.models.tasks import Task
from atlas.tasks.google import GoogleTasksAdapter
from atlas.org.orchestrator import build_context as build_org_context
from atlas.org.orchestrator import run_atlas_synthesis, run_department_heads
from atlas.evals.dataset import load_dataset
from atlas.evals.report import render_markdown
from atlas.evals.runner import run_eval
from atlas.llm.openai import OpenAIClient
from atlas.prediction.audience import build_seed, load_document, predict_audience
from atlas.prediction.mirofish import MiroFishClient
from atlas.prediction.models import SeedDocument
from atlas.prediction.stub import StubPredictionClient
from atlas.storage.sqlite import (
    connect,
    default_db_path,
    get_alerts_summary,
    get_latest_board_report,
    get_latest_daily_brief,
    get_latest_hourly_plan,
    get_latest_triage_report,
    get_task_by_pair,
    init_db,
    insert_alerts,
    insert_board_report,
    insert_daily_brief,
    insert_hourly_plan,
    insert_triage_report,
    insert_task_sync_log,
    insert_pending_action,
    insert_eval_run,
    list_alerts,
    list_pending_actions,
    list_tasks,
    get_pending_action,
    set_pending_action_status,
    upsert_task_lists,
    upsert_tasks,
)
from atlas.storage.schema import SCHEMA_VERSION
from atlas.utils.time import resolve_timezone, today_in_timezone
from atlas.board_meeting.manifest import build_manifest, write_manifest
from atlas.board_meeting.report import generate_board_report as generate_tts_report
from atlas.board_meeting.split import (
    ALLOWED_HEAD_KEYS,
    normalize_head_key,
    safe_slug,
    split_head_sections,
)
from atlas.tts.chunking import chunk_text
from atlas.tts.elevenlabs import ElevenLabsClient
from atlas.tts.voices import get_voice_id
from atlas.workflows.board_meeting import (
    board_report_payload_json,
    generate_board_report as generate_legacy_board_report,
)
from atlas.workflows.email_triage import generate_triage_report, load_messages, triage_payload_json
from atlas.workflows.hourly_planner import generate_hourly_plan, hourly_plan_payload_json
from atlas.workflows.simulation import simulate_week


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlas")
    subparsers = parser.add_subparsers(dest="command", required=True)

    daily_brief = subparsers.add_parser(
        "daily-brief",
        help="Stub for daily brief; loads config and writes a boot record.",
    )
    daily_brief.add_argument("--config", required=True, help="Path to YAML config.")
    daily_brief.add_argument(
        "--db",
        help="Override default database path.",
    )
    board_meeting = subparsers.add_parser(
        "board-meeting",
        help="Board meeting reports and audio.",
    )
    board_meeting.add_argument("--config", help="Path to YAML config (legacy).")
    board_meeting.add_argument(
        "--db",
        help="Override default database path.",
    )
    board_meeting.add_argument(
        "--enable-llm",
        action="store_true",
        help="Enable LLM-powered drafts in the report.",
    )
    bm_sub = board_meeting.add_subparsers(dest="bm_command", required=True)
    bm_report = bm_sub.add_parser("report", help="Print the board meeting report.")
    bm_report.add_argument("--db", help="Override default database path.")
    bm_report.add_argument(
        "--enable-llm",
        action="store_true",
        help="Enable LLM-powered drafts in the report.",
    )
    bm_speak = bm_sub.add_parser("speak", help="Generate MP3s for each head.")
    bm_speak.add_argument("--db", help="Override default database path.")
    bm_speak.add_argument(
        "--enable-llm",
        action="store_true",
        help="Enable LLM-powered drafts in the report.",
    )
    bm_speak.add_argument(
        "--out-dir",
        help="Output directory for MP3 files.",
    )
    bm_speak.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without calling ElevenLabs.",
    )
    bm_speak.add_argument(
        "--head",
        choices=sorted(ALLOWED_HEAD_KEYS),
        help="Generate audio for a single head.",
    )
    bm_speak.add_argument(
        "--format",
        choices=["mp3", "wav"],
        default="mp3",
        help="Audio format (default: mp3).",
    )
    alerts = subparsers.add_parser(
        "alerts",
        help="List draft alerts.",
    )
    alerts.add_argument("--db", help="Override default database path.")
    alerts.add_argument("--severity", help="Filter by severity (e.g., HIGH).")
    alerts.add_argument("--category", help="Filter by category.")
    alerts.add_argument(
        "--limit", type=int, default=20, help="Max number of alerts to list."
    )
    hourly_plan = subparsers.add_parser(
        "hourly-plan",
        help="Generate an hourly plan for today.",
    )
    hourly_plan.add_argument("--config", required=True, help="Path to YAML config.")
    hourly_plan.add_argument(
        "--db",
        help="Override default database path.",
    )
    email_triage = subparsers.add_parser(
        "email-triage",
        help="Classify messages from a local input file.",
    )
    email_triage.add_argument("--input", required=True, help="Path to messages file.")
    email_triage.add_argument(
        "--db",
        help="Override default database path.",
    )
    demo = subparsers.add_parser(
        "demo",
        help="Generate deterministic demo artifacts and populate the database.",
    )
    demo.add_argument("--config", required=True, help="Path to YAML config.")
    demo.add_argument("--db", help="Override default database path.")
    simulate = subparsers.add_parser(
        "simulate-week",
        help="Run a deterministic week simulation and verify persistence.",
    )
    simulate.add_argument("--config", required=True, help="Path to YAML config.")
    simulate.add_argument("--db", help="Override default database path.")
    simulate.add_argument(
        "--start-date",
        help="YYYY-MM-DD start date (default: today in timezone).",
    )
    doctor = subparsers.add_parser(
        "doctor",
        help="Run local diagnostics for ATLAS.",
    )
    doctor.add_argument("--db", help="Override default database path.")
    doctor.add_argument(
        "--server-url",
        default="http://127.0.0.1:7331",
        help="Base server URL for reachability check.",
    )
    tasks = subparsers.add_parser(
        "tasks",
        help="Google Tasks commands.",
    )
    tasks_sub = tasks.add_subparsers(dest="tasks_command", required=True)
    tasks_sync = tasks_sub.add_parser(
        "sync",
        help="Sync Google Tasks into the local database (read-only).",
    )
    tasks_sync.add_argument("--config", required=True, help="Path to YAML config.")
    tasks_sync.add_argument("--db", help="Override default database path.")
    tasks_list = tasks_sub.add_parser(
        "list",
        help="List tasks from the local database.",
    )
    tasks_list.add_argument("--db", help="Override default database path.")
    tasks_list.add_argument("--list-id", help="Filter by list id.")
    tasks_list.add_argument(
        "--status",
        default="needsAction",
        help="Filter by status: needsAction|completed|all.",
    )
    tasks_list.add_argument("--search", help="Search in title/notes.")
    tasks_list.add_argument("--due-before", help="Filter due before (RFC3339).")
    tasks_list.add_argument("--due-after", help="Filter due after (RFC3339).")
    tasks_list.add_argument("--limit", type=int, default=20, help="Limit results.")
    tasks_list.add_argument(
        "--json",
        action="store_true",
        help="Print tasks as JSON.",
    )
    org = subparsers.add_parser(
        "org",
        help="Run hierarchical org reports.",
    )
    org_sub = org.add_subparsers(dest="org_command", required=True)
    org_run = org_sub.add_parser("run", help="Run head reports and Atlas synthesis.")
    org_run.add_argument("--db", help="Override default database path.")
    org_run.add_argument(
        "--enable-llm",
        action="store_true",
        help="Enable LLM-powered drafts.",
    )
    org_run.add_argument(
        "--verbose",
        action="store_true",
        help="Print head reports and worker outputs.",
    )
    actions = subparsers.add_parser(
        "actions",
        help="Manage pending approvals.",
    )
    actions_sub = actions.add_subparsers(dest="actions_command", required=True)
    actions_propose = actions_sub.add_parser(
        "propose", help="Propose new approval candidates."
    )
    actions_propose.add_argument("--db", help="Override default database path.")
    actions_propose.add_argument(
        "--enable-llm",
        action="store_true",
        help="Enable LLM-powered proposals.",
    )
    actions_list = actions_sub.add_parser("list", help="List pending actions.")
    actions_list.add_argument("--db", help="Override default database path.")
    actions_list.add_argument(
        "--status", default="pending", help="Filter by status."
    )
    actions_list.add_argument("--limit", type=int, default=50, help="Limit results.")
    actions_approve = actions_sub.add_parser(
        "approve", help="Approve and execute an action."
    )
    actions_approve.add_argument("action_id", type=int, help="Pending action id.")
    actions_approve.add_argument("--db", help="Override default database path.")
    actions_reject = actions_sub.add_parser(
        "reject", help="Reject a pending action."
    )
    actions_reject.add_argument("action_id", type=int, help="Pending action id.")
    actions_reject.add_argument("--db", help="Override default database path.")
    actions_fill = actions_sub.add_parser(
        "fill", help="Convert a request_more_info action into task_complete."
    )
    actions_fill.add_argument("action_id", type=int, help="Pending action id.")
    actions_fill.add_argument("--db", help="Override default database path.")
    actions_fill.add_argument("--task-id", help="Task id to use.")
    actions_fill.add_argument("--list-id", help="List id to use.")
    actions_fill.add_argument(
        "--auto",
        action="store_true",
        help="Auto-select the best candidate task.",
    )
    predict = subparsers.add_parser(
        "predict",
        help="Rehearse real-world reactions with MiroFish.",
    )
    predict_sub = predict.add_subparsers(dest="predict_command", required=True)
    predict_audience = predict_sub.add_parser(
        "audience",
        help="Predict how an audience reacts to a message/announcement.",
    )
    predict_audience.add_argument(
        "--requirement",
        required=True,
        help="Natural-language prediction ask (e.g. 'How will staff react to this reorg?').",
    )
    predict_audience.add_argument(
        "--input",
        action="append",
        default=[],
        help="Seed document path (repeatable). Defaults to the requirement text.",
    )
    predict_audience.add_argument("--project-name", help="Optional MiroFish project name.")
    predict_audience.add_argument("--context", help="Optional additional context.")
    predict_audience.add_argument("--db", help="Override default database path.")
    predict_audience.add_argument(
        "--enable-prediction",
        action="store_true",
        help="Use the live MiroFish backend instead of the offline stub.",
    )
    predict_audience.add_argument(
        "--verbose",
        action="store_true",
        help="Log each MiroFish pipeline stage's response to stderr.",
    )
    evals = subparsers.add_parser(
        "evals",
        help="Evaluate ATLAS's LLM components against labeled datasets.",
    )
    evals_sub = evals.add_subparsers(dest="evals_command", required=True)
    evals_run = evals_sub.add_parser(
        "run", help="Score the reaction-verdict judges against the golden set."
    )
    evals_run.add_argument("--db", help="Override default database path.")
    evals_run.add_argument("--dataset", help="Path to a JSONL dataset (defaults to golden set).")
    evals_run.add_argument("--limit", type=int, help="Evaluate only the first N examples.")
    evals_run.add_argument(
        "--enable-llm",
        action="store_true",
        help="Also evaluate the LLM-as-judge (requires an LLM key).",
    )
    agents = subparsers.add_parser(
        "agents",
        help="Run AI agents and print draft outputs.",
    )
    agents_sub = agents.add_subparsers(dest="agents_command", required=True)
    agents_run = agents_sub.add_parser("run", help="Run agent drafts.")
    agents_run.add_argument("--db", help="Override default database path.")
    agents_run.add_argument(
        "--enable-llm",
        action="store_true",
        help="Enable LLM-powered drafts.",
    )
    serve = subparsers.add_parser(
        "serve",
        help="Start the local mobile integration server.",
    )
    serve.add_argument("--host", default="0.0.0.0", help="Bind host.")
    serve.add_argument("--port", type=int, default=7331, help="Bind port.")
    serve.add_argument(
        "--db",
        help="Override default database path.",
    )
    serve.add_argument(
        "--allow-lan-cors",
        action="store_true",
        help="Allow CORS for private LAN origins.",
    )
    return parser


def _load_task_candidates(conn, limit: int = 5) -> list[Task]:
    rows = list_tasks(conn, status="needsAction", limit=limit)
    return [
        Task(
            id=row["id"],
            title=row["title"],
            status=row["status"],
            due=row["due"],
            updated=row["updated"],
        )
        for row in rows
    ]


def run_daily_brief(config_path: str, db_path: str | None) -> int:
    try:
        config = load_config(config_path)
    except Exception as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    tz = resolve_timezone(config.timezone)
    day = today_in_timezone(tz)
    adapter = StubCalendarAdapter()
    events = adapter.fetch_events(day, tz)
    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        tasks = _load_task_candidates(conn)
        brief = generate_daily_brief(config, events, day, tz, tasks=tasks)
        brief_id = insert_daily_brief(conn, day.isoformat(), brief.markdown, brief.tags)
        if brief.alerts:
            insert_alerts(conn, "daily_brief", brief_id, brief.alerts)
    finally:
        conn.close()

    print(brief.markdown)
    if not tasks:
        print("Run atlas tasks sync")
    print(f"Stored daily brief in {resolved_db_path}")
    return 0


def run_board_meeting(
    config_path: str, db_path: str | None, enable_llm: bool
) -> int:
    try:
        config = load_config(config_path)
    except Exception as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    report = generate_legacy_board_report(config, enable_llm=enable_llm, db_path=db_path)
    payload_json = board_report_payload_json(report)

    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        report_id = insert_board_report(
            conn,
            report.week_start_date.isoformat(),
            report.markdown,
            payload_json,
            report.tags,
        )
        if report.alerts:
            insert_alerts(
                conn,
                "board_meeting",
                report_id,
                report.alerts,
            )
    finally:
        conn.close()

    print(report.markdown)
    print(f"Stored board report in {resolved_db_path}")
    return 0


def run_board_meeting_report(db_path: str | None, enable_llm: bool) -> int:
    report = generate_tts_report(db_path, enable_llm=enable_llm)
    print(report)
    return 0


def run_board_meeting_speak(
    db_path: str | None,
    enable_llm: bool,
    out_dir: str | None,
    dry_run: bool,
    head: str | None = None,
    audio_format: str = "mp3",
) -> int:
    report = generate_tts_report(db_path, enable_llm=enable_llm)
    sections = split_head_sections(report)
    if head:
        normalized = normalize_head_key(head)
        section = sections.get(normalized)
        if not section:
            print("Requested head section not found.", file=sys.stderr)
            return 2
        sections = {normalized: section}

    today = datetime.now(timezone.utc).date().isoformat()
    output_dir = Path(out_dir).expanduser().resolve() if out_dir else Path.home() / ".atlas" / "audio"
    manifest_entries: list[dict[str, object]] = []

    plan: list[tuple[str, int, str]] = []
    for head_key, text in sections.items():
        if not text:
            continue
        chunks = chunk_text(text, max_chars=2500)
        for idx, chunk in enumerate(chunks, start=1):
            plan.append((head_key, idx, chunk))

    if dry_run:
        for head_key, idx, chunk in plan:
            filename = f"{today}-{safe_slug(head_key)}-{idx:02d}.{audio_format}"
            chars = len(chunk)
            est_seconds = round(chars / 14.0, 1)
            print(
                f"DRY RUN: {head_key} -> {output_dir / filename} "
                f"(chunk={idx}, chars={chars}, est_seconds={est_seconds})"
            )
        return 0

    client = ElevenLabsClient.from_env()
    for head_key, idx, chunk in plan:
        voice_id = get_voice_id(head_key)
        filename = f"{today}-{safe_slug(head_key)}-{idx:02d}.{audio_format}"
        out_path = output_dir / filename
        generated = client.synthesize(chunk, voice_id, out_path, audio_format=audio_format)
        chars = len(chunk)
        est_seconds = round(chars / 14.0, 1)
        print(
            f"{generated} (head={head_key}, chunk={idx}, chars={chars}, est_seconds={est_seconds})"
        )
        manifest_entries.append(
            {
                "head": head_key,
                "chunk_index": idx,
                "path": str(generated),
                "chars": chars,
                "est_seconds": est_seconds,
                "format": audio_format,
                "voice_id_env": _voice_env_for_head(head_key),
            }
        )

    manifest = build_manifest(
        day=today,
        output_dir=output_dir,
        audio_format=audio_format,
        enable_llm=enable_llm,
        entries=manifest_entries,
    )
    manifest_path = write_manifest(output_dir, today, manifest)
    print(f"Wrote manifest: {manifest_path}")
    return 0


def _voice_env_for_head(head_key: str) -> str:
    mapping = {
        "atlas": "ELEVENLABS_VOICE_ATLAS",
        "operations": "ELEVENLABS_VOICE_OPERATIONS",
        "risk": "ELEVENLABS_VOICE_RISK",
        "finance": "ELEVENLABS_VOICE_FINANCE",
        "learning": "ELEVENLABS_VOICE_LEARNING",
    }
    return mapping.get(head_key, "")


def run_alerts(
    db_path: str | None, severity: str | None, category: str | None, limit: int
) -> int:
    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        rows = list_alerts(conn, severity=severity, category=category, limit=limit)
    finally:
        conn.close()

    if not rows:
        print("No draft alerts found.")
        return 0

    for row in rows:
        print(
            f"[{row['severity']}] {row['category']} - {row['title']} "
            f"(context: {row['context_type']}:{row['context_id']})"
        )
    return 0


def run_hourly_plan(config_path: str, db_path: str | None) -> int:
    try:
        config = load_config(config_path)
    except Exception as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    tz = resolve_timezone(config.timezone)
    day = today_in_timezone(tz)
    adapter = StubCalendarAdapter()
    events = adapter.fetch_events(day, tz)

    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        tasks = _load_task_candidates(conn)
        plan = generate_hourly_plan(config, events, day, tz, tasks=tasks)
        payload_json = hourly_plan_payload_json(plan)
        plan_id = insert_hourly_plan(
            conn, day.isoformat(), plan.markdown, payload_json, plan.tags
        )
        if plan.alerts:
            insert_alerts(conn, "hourly_plan", plan_id, plan.alerts)
    finally:
        conn.close()

    print(plan.markdown)
    if not tasks:
        print("Run atlas tasks sync")
    print(f"Stored hourly plan in {resolved_db_path}")
    return 0


def run_email_triage(input_path: str, db_path: str | None) -> int:
    try:
        messages = load_messages(input_path)
    except Exception as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2

    report = generate_triage_report(messages)
    payload_json = triage_payload_json(report)

    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        triage_id = insert_triage_report(conn, report.markdown, payload_json, report.tags)
        if report.alerts:
            insert_alerts(conn, "triage_report", triage_id, report.alerts)
    finally:
        conn.close()

    print(report.markdown)
    print(f"Stored triage report in {resolved_db_path}")
    return 0


def run_demo(config_path: str, db_path: str | None) -> int:
    try:
        config = load_config(config_path)
    except Exception as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    tz = resolve_timezone(config.timezone)
    demo_now = datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc).astimezone(tz)
    day = demo_now.date()

    adapter = StubCalendarAdapter()
    events = adapter.fetch_events(day, tz)
    brief = generate_daily_brief(config, events, day, tz)
    plan = generate_hourly_plan(config, events, day, tz)
    report = generate_board_report(config, now=demo_now)

    payload_hourly = hourly_plan_payload_json(plan)
    payload_board = board_report_payload_json(report)

    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        brief_id = insert_daily_brief(conn, day.isoformat(), brief.markdown, brief.tags)
        if brief.alerts:
            insert_alerts(conn, "daily_brief", brief_id, brief.alerts)

        plan_id = insert_hourly_plan(
            conn, day.isoformat(), plan.markdown, payload_hourly, plan.tags
        )
        if plan.alerts:
            insert_alerts(conn, "hourly_plan", plan_id, plan.alerts)

        report_id = insert_board_report(
            conn,
            report.week_start_date.isoformat(),
            report.markdown,
            payload_board,
            report.tags,
        )
        if report.alerts:
            insert_alerts(conn, "board_meeting", report_id, report.alerts)
    finally:
        conn.close()

    print(f"Demo data stored in {resolved_db_path}")
    print("You can now open /client/")
    return 0


def run_agents_command(db_path: str | None, enable_llm: bool) -> int:
    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        context = build_agent_context(conn)
    finally:
        conn.close()

    try:
        outputs = run_agents(context, enable_llm=enable_llm)
    except Exception as exc:
        print(f"Agent error: {exc}", file=sys.stderr)
        return 2

    print("# Agent Drafts")
    for name, draft in outputs.items():
        print(f"## {name}")
        print(draft)
        print("")
    return 0


def run_simulate_week(
    config_path: str, db_path: str | None, start_date: str | None
) -> int:
    try:
        config = load_config(config_path)
    except Exception as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    tz = resolve_timezone(config.timezone)
    if start_date:
        try:
            start_day = datetime.fromisoformat(start_date).date()
        except ValueError:
            print("start-date must be in YYYY-MM-DD format.", file=sys.stderr)
            return 2
    else:
        start_day = today_in_timezone(tz)

    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    try:
        summary = simulate_week(config, resolved_db_path, start_day)
    except Exception as exc:
        print(f"Simulation error: {exc}", file=sys.stderr)
        return 2

    print(f"Simulation complete. DB: {resolved_db_path}")
    for table, info in summary.items():
        print(f"{table}: {info['count']} (latest: {info['latest'] or 'None'})")
    return 0


def _check_health(server_url: str) -> tuple[bool, str]:
    parsed = urlparse(server_url)
    if not parsed.scheme or not parsed.netloc:
        return False, "Invalid server URL."
    health_url = server_url.rstrip("/") + "/health"
    try:
        req = Request(health_url, method="GET")
        with urlopen(req, timeout=0.5) as response:
            return response.status == 200, ""
    except URLError as exc:
        return False, str(exc.reason)


def _check_status(
    server_url: str, token: str | None
) -> tuple[int | None, dict | None, str]:
    parsed = urlparse(server_url)
    if not parsed.scheme or not parsed.netloc:
        return None, None, "Invalid server URL."
    status_url = server_url.rstrip("/") + "/api/v1/status"
    headers = {}
    if token:
        headers["X-ATLAS-TOKEN"] = token
    try:
        req = Request(status_url, headers=headers, method="GET")
        with urlopen(req, timeout=0.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, payload, ""
    except HTTPError as exc:
        return exc.code, None, str(exc.reason)
    except URLError as exc:
        return None, None, str(exc.reason)


def run_doctor(db_path: str | None, server_url: str) -> int:
    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        latest_daily = get_latest_daily_brief(conn)
        latest_hourly = get_latest_hourly_plan(conn)
        latest_board = get_latest_board_report(conn)
        latest_triage = get_latest_triage_report(conn)
        alerts_summary = get_alerts_summary(conn)
    finally:
        conn.close()

    token = os.environ.get("ATLAS_MOBILE_TOKEN")
    health_ok, health_error = _check_health(server_url)
    status_code, status_payload, status_error = _check_status(server_url, token)
    status_payload_ok = bool(
        status_payload
        and isinstance(status_payload, dict)
        and {"time", "db_path", "schema_version"}.issubset(status_payload)
    )
    token_missing = not token

    print("ATLAS Doctor")
    print("")
    print(f"DB Path: {resolved_db_path}")
    print(f"Schema Version: {SCHEMA_VERSION}")
    print(
        f"Server Health: {'OK' if health_ok else 'NO'} ({server_url})"
        + (f" - {health_error}" if health_error else "")
    )
    if status_code is None:
        print(f"API Status: Unavailable - {status_error}")
    elif status_code == 200:
        print("API Status: OK (200)")
    elif status_code == 401:
        print("API Status: Unauthorized (401)")
    else:
        print(f"API Status: Error ({status_code})")
    print(f"Shell Token: {'SET' if token else 'MISSING'}")
    mirofish_url = os.environ.get("MIROFISH_BASE_URL", "http://localhost:5001")
    mirofish_ok, mirofish_error = _check_health(mirofish_url)
    print(
        f"MiroFish Backend: {'OK' if mirofish_ok else 'NO'} ({mirofish_url})"
        + (f" - {mirofish_error}" if mirofish_error else "")
    )
    print("")
    print(f"Latest Daily Brief: {latest_daily['timestamp'] if latest_daily else 'None'}")
    print(f"Latest Hourly Plan: {latest_hourly['created_at'] if latest_hourly else 'None'}")
    print(f"Latest Board Meeting: {latest_board['created_at'] if latest_board else 'None'}")
    print(f"Latest Triage Report: {latest_triage['created_at'] if latest_triage else 'None'}")
    print(
        "Alerts: "
        + (
            f"{alerts_summary['count']} total, latest {alerts_summary['latest']}"
            if alerts_summary["latest"]
            else "None"
        )
    )
    print("")
    print("Hints:")
    if not health_ok:
        print("- Server not reachable; ensure `atlas serve` is running and port is open.")
    if status_code == 401:
        if token:
            print("- Server reachable, but token was rejected; verify ATLAS_MOBILE_TOKEN matches the server.")
        else:
            print("- Server reachable; token required for /api/v1/* endpoints.")
    if status_code == 200 and not token:
        print("- Server reachable without token; check auth configuration.")
    if token_missing and (not health_ok or not server_url):
        print("- ATLAS_MOBILE_TOKEN is missing; set it before running `atlas serve`.")
    if not mirofish_ok:
        print(
            "- MiroFish backend not reachable; `predict audience` uses the offline stub. "
            "Run MiroFish locally (github.com/666ghj/MiroFish) and set MIROFISH_BASE_URL "
            "to use --enable-prediction."
        )
    if server_url.rstrip("/").endswith("/client"):
        print("- Server URL must be the base URL, not /client.")
    if status_code == 200 and not status_payload_ok:
        print("- Status payload missing expected fields; check server response.")
    print("- Server URL must be base URL (no /client).")
    return 0


def run_tasks_sync(config_path: str, db_path: str | None) -> int:
    try:
        load_config(config_path)
    except Exception as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    try:
        adapter = GoogleTasksAdapter.from_env()
    except Exception as exc:
        print(f"Tasks auth error: {exc}", file=sys.stderr)
        return 2

    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        task_lists = adapter.list_task_lists()
        upsert_task_lists(conn, task_lists)
        total_tasks = 0
        for task_list in task_lists:
            tasks = adapter.list_tasks(task_list.id)
            upsert_tasks(conn, task_list.id, tasks)
            total_tasks += len(tasks)
        insert_task_sync_log(conn, len(task_lists), total_tasks, "google")
    finally:
        conn.close()

    print(f"Synced {len(task_lists)} lists and {total_tasks} tasks.")
    print(f"DB: {resolved_db_path}")
    return 0


def run_tasks_list(
    db_path: str | None,
    list_id: str | None,
    status: str,
    search: str | None,
    due_before: str | None,
    due_after: str | None,
    limit: int,
    as_json: bool,
) -> int:
    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        rows = list_tasks(
            conn,
            list_id=list_id,
            status=status,
            due_before=due_before,
            due_after=due_after,
            search=search,
            limit=limit,
        )
    finally:
        conn.close()

    if not rows:
        print("No tasks found.")
        return 0
    if as_json:
        payload = [
            {
                "id": row["id"],
                "title": row["title"],
                "due": row["due"],
                "status": row["status"],
                "list_id": row["list_id"],
            }
            for row in rows
        ]
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    for row in rows:
        due = row["due"] or "No due date"
        print(
            f"- {row['title']} ({row['status']}, due: {due}) "
            f"task_id={row['id']} list_id={row['list_id']}"
        )
    return 0


def _run_org_pipeline(
    db_path: str | None, enable_llm: bool
) -> tuple[dict, list]:
    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        context = build_org_context(conn)
    finally:
        conn.close()

    try:
        head_reports = run_department_heads(context, enable_llm=enable_llm)
    except Exception as exc:
        raise RuntimeError(f"Org run failed: {exc}") from exc
    synthesis = run_atlas_synthesis(context, head_reports)
    return synthesis, head_reports


def run_org(db_path: str | None, enable_llm: bool, verbose: bool) -> int:
    try:
        synthesis, head_reports = _run_org_pipeline(db_path, enable_llm)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if verbose:
        print("# Head Reports")
        for report in head_reports:
            print(f"## {report.head_name}")
            print(f"- Summary: {report.domain_summary}")
            print(f"- Confidence: {report.confidence}")
            if report.uncertainties:
                print("- Uncertainties:")
                for item in report.uncertainties:
                    print(f"  - {item}")
            if report.key_risks:
                print("- Key Risks:")
                for item in report.key_risks:
                    print(f"  - {item}")
            if report.recommendations_for_atlas:
                print("- Recommendations:")
                for item in report.recommendations_for_atlas:
                    print(f"  - {item}")
            traces = report.worker_trace[:2]
            if traces:
                print("- Worker Outputs:")
                for trace in traces:
                    parsed = trace.get("parsed_output")
                    if isinstance(parsed, dict):
                        summary = parsed.get("summary", "")
                        confidence = parsed.get("confidence", "")
                        uncertainties = parsed.get("uncertainties", [])
                        print(f"  - {summary}")
                        print(f"    Confidence: {confidence}")
                        if uncertainties:
                            print(f"    Uncertainties: {', '.join(uncertainties)}")
                    else:
                        result = trace.get("result", {})
                        output = result.get("output", "")
                        confidence = result.get("confidence", "")
                        uncertainties = result.get("uncertainties", [])
                        print(f"  - {output}")
                        print(f"    Confidence: {confidence}")
                        if uncertainties:
                            print(f"    Uncertainties: {', '.join(uncertainties)}")
            print("")

    print("# Atlas Synthesis")
    print("## What mattered")
    for item in synthesis["what_mattered"]:
        print(f"- {item}")
    print("## What happens next")
    for item in synthesis["what_happens_next"]:
        print(f"- {item}")
    print("## Approval candidates")
    if not synthesis["approval_candidates"]:
        print("- None")
    else:
        for candidate in synthesis["approval_candidates"]:
            print(
                f"- {candidate['action_type']} from {candidate['source_head']}: "
                f"{candidate['reason']}"
            )
    return 0


def run_actions_propose(db_path: str | None, enable_llm: bool) -> int:
    try:
        synthesis, _ = _run_org_pipeline(db_path, enable_llm)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    candidates = synthesis["approval_candidates"]
    if not candidates:
        print("No approval candidates.")
        return 0

    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        for candidate in candidates:
            try:
                parse_action(candidate["action_type"], candidate["payload"])
            except Exception as exc:
                print(f"Skipped invalid candidate: {exc}")
                continue
            payload = {
                "action": candidate["payload"],
                "reason": candidate["reason"],
                "source_head": candidate["source_head"],
            }
            action_id = insert_pending_action(
                conn, "atlas", candidate["action_type"], payload
            )
            print(
                f"Inserted action {action_id}: {candidate['action_type']} "
                f"from {candidate['source_head']}"
            )
    finally:
        conn.close()
    return 0


def run_actions_list(db_path: str | None, status: str, limit: int) -> int:
    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        rows = list_pending_actions(conn, status=status, limit=limit)
    finally:
        conn.close()

    if not rows:
        print("No actions found.")
        return 0
    for row in rows:
        reason = ""
        payload = row.get("payload", {})
        if isinstance(payload, dict):
            reason = payload.get("reason", "")
        reason_part = f" - {reason}" if reason else ""
        print(
            f"[{row['status']}] {row['id']} {row['action_type']} "
            f"(source: {row['source']}){reason_part}"
        )
    return 0


def run_actions_approve(db_path: str | None, action_id: int) -> int:
    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        action = get_pending_action(conn, action_id)
        if not action:
            print("Action not found.", file=sys.stderr)
            return 2
        if action["status"] != "pending":
            print("Action is not pending.", file=sys.stderr)
            return 2
        set_pending_action_status(conn, action_id, "approved")
    finally:
        conn.close()

    payload = action.get("payload", {})
    if not isinstance(payload, dict) or "action" not in payload:
        error_msg = "Invalid action payload."
        conn = connect(resolved_db_path)
        try:
            init_db(conn)
            set_pending_action_status(conn, action_id, "failed", error_msg)
        finally:
            conn.close()
        print(error_msg, file=sys.stderr)
        return 2

    if action["action_type"] == "request_more_info":
        conn = connect(resolved_db_path)
        try:
            init_db(conn)
            set_pending_action_status(conn, action_id, "executed")
        finally:
            conn.close()
        question = payload["action"].get("question", "Missing question.")
        needed = payload["action"].get("needed_fields", [])
        print(f"Request: {question}")
        if needed:
            print(f"Needed fields: {', '.join(needed)}")
        return 0

    try:
        adapter = GoogleTasksAdapter.from_env()
        execute_action(action["action_type"], payload["action"], adapter)
    except Exception as exc:
        message = str(exc)[:200]
        conn = connect(resolved_db_path)
        try:
            init_db(conn)
            set_pending_action_status(conn, action_id, "failed", message)
        finally:
            conn.close()
        print(f"Execution failed: {message}", file=sys.stderr)
        return 2

    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        set_pending_action_status(conn, action_id, "executed")
    finally:
        conn.close()
    print(f"Action {action_id} executed.")
    return 0


def run_predict_audience(
    db_path: str | None,
    inputs: list[str],
    requirement: str,
    enable_prediction: bool,
    project_name: str | None,
    context: str | None,
    verbose: bool = False,
) -> int:
    documents: list[SeedDocument] = []
    for raw_path in inputs:
        path = Path(raw_path).expanduser()
        if not path.is_file():
            print(f"Input file not found: {path}", file=sys.stderr)
            return 2
        documents.append(load_document(path))

    if enable_prediction:
        client = MiroFishClient.from_env(verbose=verbose)
    else:
        client = StubPredictionClient()

    seed = build_seed(requirement, documents, project_name, context)

    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        try:
            result = predict_audience(client, conn, seed)
        except Exception as exc:
            print(f"Prediction failed: {str(exc)[:300]}", file=sys.stderr)
            return 2
    finally:
        conn.close()

    print(result.report_markdown)
    print("")
    print(f"Reaction risk: {result.verdict} (score {result.risk_score:.2f})")
    if result.simulation_id:
        print(
            f"Explore the simulated world: {result.simulation_id} "
            "(open the MiroFish frontend to chat with agents)."
        )
    return 0


def run_evals_run(
    db_path: str | None,
    dataset: str | None,
    limit: int | None,
    enable_llm: bool,
) -> int:
    try:
        examples = load_dataset(dataset)
    except (OSError, ValueError) as exc:
        print(f"Failed to load dataset: {exc}", file=sys.stderr)
        return 2
    if limit is not None:
        examples = examples[:limit]
    if not examples:
        print("Dataset is empty.", file=sys.stderr)
        return 2

    llm = None
    if enable_llm:
        try:
            llm = OpenAIClient.from_env()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    dataset_name = Path(dataset).stem if dataset else "reaction_golden"
    report = run_eval(examples, llm=llm, dataset=dataset_name)
    print(render_markdown(report))

    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        insert_eval_run(conn, report)
    finally:
        conn.close()
    return 0


def run_actions_reject(db_path: str | None, action_id: int) -> int:
    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        action = get_pending_action(conn, action_id)
        if not action:
            print("Action not found.", file=sys.stderr)
            return 2
        if action["status"] != "pending":
            print("Action is not pending.", file=sys.stderr)
            return 2
        set_pending_action_status(conn, action_id, "rejected")
    finally:
        conn.close()
    print(f"Action {action_id} rejected.")
    return 0


def _pick_task_interactive(rows: list[dict]) -> dict | None:
    if not rows:
        print("No tasks available.", file=sys.stderr)
        return None
    for idx, row in enumerate(rows, start=1):
        due = row["due"] or "No due date"
        print(
            f"{idx}) {row['title']} (due: {due}) "
            f"[task_id={row['id']} list_id={row['list_id']}]"
        )
    choice = input("Select a task number: ").strip()
    try:
        selection = int(choice)
    except ValueError:
        print("Invalid selection.", file=sys.stderr)
        return None
    if selection < 1 or selection > len(rows):
        print("Selection out of range.", file=sys.stderr)
        return None
    return rows[selection - 1]


def run_actions_fill(
    db_path: str | None,
    action_id: int,
    task_id: str | None,
    list_id: str | None,
    auto: bool,
) -> int:
    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        action = get_pending_action(conn, action_id)
        if not action:
            print("Action not found.", file=sys.stderr)
            return 2
        if action["status"] != "pending":
            print("Action is not pending.", file=sys.stderr)
            return 2
        if action["action_type"] != "request_more_info":
            print("Action is not request_more_info.", file=sys.stderr)
            return 2

        if task_id and list_id:
            task_row = get_task_by_pair(conn, list_id, task_id)
            if not task_row:
                print("Task pair not found in DB.", file=sys.stderr)
                return 2
        else:
            rows = list_tasks(conn, status="needsAction", limit=10)
            if not rows:
                print("No tasks available.", file=sys.stderr)
                return 2
            if auto:
                task_row = rows[0]
            else:
                task_row = _pick_task_interactive(rows)
                if task_row is None:
                    return 2
            task_id = task_row["id"]
            list_id = task_row["list_id"]

        payload = action.get("payload", {})
        source_head = payload.get("source_head") if isinstance(payload, dict) else None
        new_payload = {
            "action": {
                "list_id": list_id,
                "task_id": task_id,
                "note": "Filled from request_more_info",
            },
            "reason": "Resolved request_more_info",
            "source_head": source_head,
        }
        new_id = insert_pending_action(conn, action["source"], "task_complete", new_payload)
        set_pending_action_status(
            conn, action_id, "rejected", f"Converted into action {new_id}"
        )
    finally:
        conn.close()

    print(f"Created task_complete action {new_id} from request_more_info {action_id}")
    return 0


def _discover_lan_addresses() -> list[str]:
    addresses: set[str] = set()
    hostname = socket.gethostname()
    for family, _, _, _, sockaddr in socket.getaddrinfo(hostname, None):
        ip = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if ip_obj.is_private and not ip_obj.is_loopback:
            addresses.add(ip)
    return sorted(addresses)


def run_serve(host: str, port: int, db_path: str | None, allow_lan_cors: bool) -> int:
    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    token = os.environ.get("ATLAS_MOBILE_TOKEN", "")
    if not token:
        print("ATLAS_MOBILE_TOKEN is required to start the server.", file=sys.stderr)
        return 2
    server = create_server(host, port, resolved_db_path, token, allow_lan_cors)
    print("Local network only. Token required.")
    print(f"Listening on http://{host}:{port}")
    if host in {"0.0.0.0", "0.0.0.0/0"}:
        for ip in _discover_lan_addresses():
            print(f"LAN: http://{ip}:{port}")
            print(f"Client URL: http://{ip}:{port}/client/")
    else:
        print(f"Client URL: http://{host}:{port}/client/")
    server.serve_forever()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "daily-brief":
        return run_daily_brief(args.config, args.db)
    if args.command == "board-meeting":
        if args.bm_command == "report":
            return run_board_meeting_report(args.db, args.enable_llm)
        if args.bm_command == "speak":
            return run_board_meeting_speak(
                args.db,
                args.enable_llm,
                args.out_dir,
                args.dry_run,
                args.head,
                args.format,
            )
        print("Unknown board-meeting command.", file=sys.stderr)
        return 2
    if args.command == "alerts":
        return run_alerts(args.db, args.severity, args.category, args.limit)
    if args.command == "hourly-plan":
        return run_hourly_plan(args.config, args.db)
    if args.command == "email-triage":
        return run_email_triage(args.input, args.db)
    if args.command == "demo":
        return run_demo(args.config, args.db)
    if args.command == "simulate-week":
        return run_simulate_week(args.config, args.db, args.start_date)
    if args.command == "doctor":
        return run_doctor(args.db, args.server_url)
    if args.command == "tasks":
        if args.tasks_command == "sync":
            return run_tasks_sync(args.config, args.db)
        if args.tasks_command == "list":
            return run_tasks_list(
                args.db,
                args.list_id,
                args.status,
                args.search,
                args.due_before,
                args.due_after,
                args.limit,
                args.json,
            )
        print("Unknown tasks command.", file=sys.stderr)
        return 2
    if args.command == "agents":
        if args.agents_command == "run":
            return run_agents_command(args.db, args.enable_llm)
        print("Unknown agents command.", file=sys.stderr)
        return 2
    if args.command == "org":
        if args.org_command == "run":
            return run_org(args.db, args.enable_llm, args.verbose)
        print("Unknown org command.", file=sys.stderr)
        return 2
    if args.command == "actions":
        if args.actions_command == "propose":
            return run_actions_propose(args.db, args.enable_llm)
        if args.actions_command == "list":
            return run_actions_list(args.db, args.status, args.limit)
        if args.actions_command == "approve":
            return run_actions_approve(args.db, args.action_id)
        if args.actions_command == "reject":
            return run_actions_reject(args.db, args.action_id)
        if args.actions_command == "fill":
            return run_actions_fill(
                args.db,
                args.action_id,
                args.task_id,
                args.list_id,
                args.auto,
            )
        print("Unknown actions command.", file=sys.stderr)
        return 2
    if args.command == "predict":
        if args.predict_command == "audience":
            return run_predict_audience(
                args.db,
                args.input,
                args.requirement,
                args.enable_prediction,
                args.project_name,
                args.context,
                args.verbose,
            )
        print("Unknown predict command.", file=sys.stderr)
        return 2
    if args.command == "evals":
        if args.evals_command == "run":
            return run_evals_run(args.db, args.dataset, args.limit, args.enable_llm)
        print("Unknown evals command.", file=sys.stderr)
        return 2
    if args.command == "serve":
        return run_serve(args.host, args.port, args.db, args.allow_lan_cors)

    print(f"Unknown command: {args.command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
