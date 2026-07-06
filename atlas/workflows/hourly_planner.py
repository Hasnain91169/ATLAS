from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, tzinfo

from atlas.brief.generator import ScheduleBlock, build_schedule
from atlas.brief.scoring import Priority, score_priorities
from atlas.models.calendar import CalendarEvent
from atlas.models.core import AtlasConfig
from atlas.models.tasks import Task
from atlas.risk.alerts import AlertDraft
from atlas.risk.rules import RiskSignals, evaluate_risks
from atlas.utils.time import combine_date_time

MEETING_HEAVY_MINUTES = 180
BUFFER_MINUTES = 10
FOCUS_CHUNK_MINUTES = 30
MIN_PRIORITY_FOCUS_MINUTES = 60


@dataclass(frozen=True)
class HourlyPlanBlock:
    start: datetime
    end: datetime
    label: str
    kind: str
    priority: str | None = None


@dataclass(frozen=True)
class HourlyPlan:
    day: date
    markdown: str
    payload: dict
    tags: list[str]
    warnings: list[str]
    alerts: list[AlertDraft]


def _block_minutes(start: datetime, end: datetime) -> int:
    return max(0, int((end - start) / timedelta(minutes=1)))


def _summarize_minutes(blocks: list[ScheduleBlock]) -> tuple[int, int]:
    meeting_minutes = 0
    focus_minutes = 0
    for block in blocks:
        duration = _block_minutes(block.start, block.end)
        if block.kind == "meeting":
            meeting_minutes += duration
        else:
            focus_minutes += duration
    return meeting_minutes, focus_minutes


def _allocate_focus_blocks(
    block: ScheduleBlock,
    focus_queue: list[tuple[str, str | None]],
    meeting_heavy: bool,
    queue_index: int,
    allocations: dict[str, int],
) -> tuple[list[HourlyPlanBlock], int]:
    segments: list[HourlyPlanBlock] = []
    remaining = _block_minutes(block.start, block.end)
    cursor = block.start
    if meeting_heavy and remaining >= (BUFFER_MINUTES + FOCUS_CHUNK_MINUTES):
        buffer_end = cursor + timedelta(minutes=BUFFER_MINUTES)
        segments.append(
            HourlyPlanBlock(
                start=cursor,
                end=buffer_end,
                label="Buffer / break",
                kind="buffer",
            )
        )
        cursor = buffer_end
        remaining -= BUFFER_MINUTES

    if not focus_queue or remaining <= 0:
        return segments, queue_index

    while remaining > 0:
        duration = min(FOCUS_CHUNK_MINUTES, remaining)
        label, focus_target = focus_queue[queue_index % len(focus_queue)]
        segment_end = cursor + timedelta(minutes=duration)
        segments.append(
            HourlyPlanBlock(
                start=cursor,
                end=segment_end,
                label=label,
                kind="focus",
                priority=focus_target,
            )
        )
        if focus_target:
            allocations[focus_target] = allocations.get(focus_target, 0) + duration
        remaining -= duration
        cursor = segment_end
        queue_index += 1
    return segments, queue_index


def _build_focus_queue(
    priorities: list[Priority], tasks: list[Task]
) -> list[tuple[str, str | None]]:
    queue: list[tuple[str, str | None]] = [
        (f"Focus: {priority.title}", priority.title) for priority in priorities
    ]
    for task in tasks:
        queue.append((f"Task: {task.title}", task.title))
    return queue


def _build_hourly_blocks(
    schedule_blocks: list[ScheduleBlock],
    priorities: list[Priority],
    tasks: list[Task],
) -> tuple[list[HourlyPlanBlock], dict[str, int], bool]:
    meeting_minutes, focus_minutes = _summarize_minutes(schedule_blocks)
    meeting_heavy = meeting_minutes >= MEETING_HEAVY_MINUTES
    allocations: dict[str, int] = {}
    hourly_blocks: list[HourlyPlanBlock] = []
    queue_index = 0
    focus_queue = _build_focus_queue(priorities, tasks)

    for block in schedule_blocks:
        if block.kind == "meeting":
            hourly_blocks.append(
                HourlyPlanBlock(
                    start=block.start,
                    end=block.end,
                    label=block.label,
                    kind="meeting",
                )
            )
            continue
        focus_segments, queue_index = _allocate_focus_blocks(
            block, focus_queue, meeting_heavy, queue_index, allocations
        )
        hourly_blocks.extend(focus_segments)

    return hourly_blocks, allocations, meeting_heavy


def _render_markdown(
    day: date,
    blocks: list[HourlyPlanBlock],
    warnings: list[str],
    alerts: list[AlertDraft],
) -> str:
    lines: list[str] = []
    lines.append(f"# Hourly Plan - {day.isoformat()}")
    lines.append("")
    lines.append("## Hourly Plan")
    for block in blocks:
        start = block.start.strftime("%H:%M")
        end = block.end.strftime("%H:%M")
        lines.append(f"- {start}-{end} {block.label}")
    lines.append("")
    if warnings:
        lines.append("## Ops Warnings")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")
    lines.append("## Risk & Compliance")
    if alerts:
        for alert in alerts:
            lines.append(f"- {alert.title} ({alert.severity})")
            for line in alert.message_markdown.splitlines():
                lines.append(f"  {line}")
    else:
        lines.append("- No draft alerts.")
    lines.append("")
    return "\n".join(lines)


def generate_hourly_plan(
    config: AtlasConfig,
    events: list[CalendarEvent],
    day: date,
    tz: tzinfo,
    tasks: list[Task] | None = None,
) -> HourlyPlan:
    schedule_blocks = build_schedule(config.working_hours, day, tz, events)
    meeting_minutes, focus_minutes = _summarize_minutes(schedule_blocks)
    priorities = score_priorities(config.goals, events, focus_minutes)[:3]
    working_hours_minutes = int(
        (
            combine_date_time(day, config.working_hours.end, tz)
            - combine_date_time(day, config.working_hours.start, tz)
        ).total_seconds()
        / 60
    )
    task_candidates = [
        task for task in (tasks or []) if task.status == "needsAction"
    ][:3]
    hourly_blocks, allocations, meeting_heavy = _build_hourly_blocks(
        schedule_blocks, priorities, task_candidates
    )

    warnings: list[str] = []
    overloaded = focus_minutes < (len(priorities) * MIN_PRIORITY_FOCUS_MINUTES)
    if meeting_heavy:
        warnings.append("Meeting-heavy day; buffer time inserted.")
    if overloaded:
        warnings.append("Overloaded: insufficient focus time for top priorities.")

    signals = RiskSignals(
        meeting_minutes=meeting_minutes,
        focus_minutes=focus_minutes,
        working_hours_minutes=working_hours_minutes,
        priorities_count=len(priorities),
        overcapacity_flags=1 if overloaded else 0,
    )
    alerts = evaluate_risks(signals)

    tags = ["hourly-plan"]
    if meeting_heavy:
        tags.append("meeting-heavy")
    if overloaded:
        tags.append("overloaded")

    payload_blocks = [
        {
            "start": block.start.isoformat(),
            "end": block.end.isoformat(),
            "label": block.label,
            "kind": block.kind,
            "priority": block.priority,
        }
        for block in hourly_blocks
    ]
    payload = {
        "date": day.isoformat(),
        "blocks": payload_blocks,
        "allocations_minutes": allocations,
        "warnings": warnings,
        "risk_signals": asdict(signals),
    }
    markdown = _render_markdown(day, hourly_blocks, warnings, alerts)
    return HourlyPlan(
        day=day,
        markdown=markdown,
        payload=payload,
        tags=tags,
        warnings=warnings,
        alerts=alerts,
    )


def hourly_plan_payload_json(plan: HourlyPlan) -> str:
    return json.dumps(plan.payload, sort_keys=True)
