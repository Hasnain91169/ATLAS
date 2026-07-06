from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo

from atlas.brief.scoring import Priority, score_priorities
from atlas.brief.tags import derive_tags
from atlas.models.calendar import CalendarEvent
from atlas.models.core import AtlasConfig, WorkingHours
from atlas.models.tasks import Task
from atlas.risk.alerts import AlertDraft
from atlas.risk.rules import RiskSignals, evaluate_risks
from atlas.utils.time import combine_date_time




@dataclass(frozen=True)
class ScheduleBlock:
    start: datetime
    end: datetime
    label: str
    kind: str


@dataclass(frozen=True)
class SuggestedAction:
    text: str
    effort_minutes: int
    priority_title: str
    rationale: str


@dataclass(frozen=True)
class DailyBrief:
    day: date
    timezone: str
    markdown: str
    tags: list[str]
    priorities: list[Priority]
    actions: list[SuggestedAction]
    alerts: list[AlertDraft]
    tasks: list[Task]


def _clamp_event(
    event: CalendarEvent, start_dt: datetime, end_dt: datetime
) -> tuple[datetime, datetime] | None:
    if event.end <= start_dt or event.start >= end_dt:
        return None
    return max(event.start, start_dt), min(event.end, end_dt)


def build_schedule(
    working_hours: WorkingHours,
    day: date,
    tz: tzinfo,
    events: list[CalendarEvent],
) -> list[ScheduleBlock]:
    start_dt = combine_date_time(day, working_hours.start, tz)
    end_dt = combine_date_time(day, working_hours.end, tz)

    blocks: list[ScheduleBlock] = []
    cursor = start_dt
    for event in sorted(events, key=lambda item: item.start):
        clamped = _clamp_event(event, start_dt, end_dt)
        if clamped is None:
            continue
        event_start, event_end = clamped
        if event_start > cursor:
            blocks.append(
                ScheduleBlock(
                    start=cursor,
                    end=event_start,
                    label="Focus time",
                    kind="focus",
                )
            )
        if event_end <= cursor:
            continue
        blocks.append(
            ScheduleBlock(
                start=event_start,
                end=event_end,
                label=f"Meeting: {event.title}",
                kind="meeting",
            )
        )
        cursor = max(cursor, event_end)
    if cursor < end_dt:
        blocks.append(
            ScheduleBlock(
                start=cursor,
                end=end_dt,
                label="Focus time",
                kind="focus",
            )
        )
    return blocks


def _minutes_between(start: datetime, end: datetime) -> int:
    return max(0, int((end - start) / timedelta(minutes=1)))


def _summarize_minutes(blocks: list[ScheduleBlock]) -> tuple[int, int]:
    meeting_minutes = 0
    focus_minutes = 0
    for block in blocks:
        duration = _minutes_between(block.start, block.end)
        if block.kind == "meeting":
            meeting_minutes += duration
        else:
            focus_minutes += duration
    return meeting_minutes, focus_minutes


def suggest_actions(priorities: list[Priority]) -> list[SuggestedAction]:
    actions: list[SuggestedAction] = []
    for priority in priorities[:3]:
        actions.append(
            SuggestedAction(
                text=f"Block 60 minutes to advance: {priority.title}",
                effort_minutes=60,
                priority_title=priority.title,
                rationale="Protects focus time against a busy calendar.",
            )
        )
    return actions


def render_markdown(
    day: date,
    timezone: str,
    blocks: list[ScheduleBlock],
    priorities: list[Priority],
    actions: list[SuggestedAction],
    alerts: list[AlertDraft],
    tasks: list[Task] | None = None,
) -> str:
    tasks = tasks or []
    lines: list[str] = []
    lines.append(f"# ATLAS Daily Brief - {day.isoformat()}")
    lines.append(f"Timezone: {timezone}")
    lines.append("")
    lines.append("## Today's Schedule")
    for block in blocks:
        start = block.start.strftime("%H:%M")
        end = block.end.strftime("%H:%M")
        lines.append(f"- {start}-{end} {block.label}")
    lines.append("")
    lines.append("## Top 3 Priorities")
    for idx, priority in enumerate(priorities[:3], start=1):
        lines.append(f"{idx}. {priority.title} (Score: {priority.score})")
        lines.append(f"   - Sources: {', '.join(priority.sources)}")
        lines.append(f"   - Why: {priority.rationale}")
    lines.append("")
    lines.append("## Tasks (Google)")
    if tasks:
        for task in tasks:
            due = task.due or "No due date"
            lines.append(f"- {task.title} (due: {due})")
    else:
        lines.append("- No tasks synced.")
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
    lines.append("## Suggested Actions")
    for idx, action in enumerate(actions[:3], start=1):
        lines.append(
            f"{idx}. {action.text} (Effort: {action.effort_minutes}m) "
            f"- supports \"{action.priority_title}\""
        )
        lines.append(f"   - Rationale: {action.rationale}")
    lines.append("")
    return "\n".join(lines)


def generate_daily_brief(
    config: AtlasConfig,
    events: list[CalendarEvent],
    day: date,
    tz: tzinfo,
    tasks: list[Task] | None = None,
) -> DailyBrief:
    blocks = build_schedule(config.working_hours, day, tz, events)
    meeting_minutes, focus_minutes = _summarize_minutes(blocks)
    working_hours_minutes = int(
        (combine_date_time(day, config.working_hours.end, tz)
        - combine_date_time(day, config.working_hours.start, tz)).total_seconds()
        / 60
    )
    signals = RiskSignals(
        meeting_minutes=meeting_minutes,
        focus_minutes=focus_minutes,
        working_hours_minutes=working_hours_minutes,
        priorities_count=len(config.goals),
    )
    alerts = evaluate_risks(signals)
    priorities = score_priorities(config.goals, events, focus_minutes)
    actions = suggest_actions(priorities)
    tags = derive_tags(meeting_minutes, focus_minutes)
    selected_tasks = _select_tasks(tasks or [])
    markdown = render_markdown(
        day, config.timezone, blocks, priorities, actions, alerts, selected_tasks
    )
    return DailyBrief(
        day=day,
        timezone=config.timezone,
        markdown=markdown,
        tags=tags,
        priorities=priorities,
        actions=actions,
        alerts=alerts,
        tasks=selected_tasks,
    )


def _select_tasks(tasks: list[Task], limit: int = 5) -> list[Task]:
    filtered = [task for task in tasks if task.status == "needsAction"]
    return sorted(
        filtered,
        key=lambda task: (
            task.due is None,
            task.due or "",
            task.updated or "",
            task.title,
        ),
    )[:limit]
