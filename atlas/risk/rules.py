from __future__ import annotations

from dataclasses import asdict, dataclass

from atlas.risk.alerts import AlertDraft, build_alert

BURNOUT_MEETING_MINUTES = 240
BURNOUT_LOW_FOCUS_MINUTES = 90
BURNOUT_OVERCAPACITY_FLAGS = 2

OVERCOMMITMENT_PRIORITIES = 4
OVERCOMMITMENT_MEETING_RATIO = 0.6
OVERCOMMITMENT_ABSOLUTE_MEETING_MINUTES = 300


@dataclass(frozen=True)
class RiskSignals:
    meeting_minutes: int = 0
    focus_minutes: int = 0
    working_hours_minutes: int = 0
    priorities_count: int = 0
    overcapacity_flags: int = 0
    missed_prayer_windows: int = 0
    health_fatigue: bool = False
    health_pain: bool = False
    finance_anomaly: bool = False


def evaluate_risks(signals: RiskSignals) -> list[AlertDraft]:
    alerts: list[AlertDraft] = []
    alerts.extend(_burnout_risk(signals))
    alerts.extend(_overcommitment_risk(signals))
    alerts.extend(_faith_risk(signals))
    alerts.extend(_health_risk(signals))
    alerts.extend(_finance_risk(signals))
    return alerts


def should_veto(alerts: list[AlertDraft]) -> bool:
    return any(alert.severity == "HIGH" for alert in alerts)


def _burnout_risk(signals: RiskSignals) -> list[AlertDraft]:
    triggers = []
    if signals.meeting_minutes >= BURNOUT_MEETING_MINUTES:
        triggers.append(f"Meeting load {signals.meeting_minutes}m")
    if signals.focus_minutes <= BURNOUT_LOW_FOCUS_MINUTES:
        triggers.append(f"Focus time {signals.focus_minutes}m")
    if signals.overcapacity_flags >= BURNOUT_OVERCAPACITY_FLAGS:
        triggers.append(f"Overcapacity flags {signals.overcapacity_flags}")
    if not triggers:
        return []
    severity = "HIGH" if signals.focus_minutes <= 30 or signals.meeting_minutes >= 360 else "MEDIUM"
    threshold = (
        f"Meeting minutes >= {BURNOUT_MEETING_MINUTES} or "
        f"focus minutes <= {BURNOUT_LOW_FOCUS_MINUTES} or "
        f"overcapacity flags >= {BURNOUT_OVERCAPACITY_FLAGS}"
    )
    mitigation = "Cap meetings, protect a 2h focus block, and trim optional scope."
    payload = {
        "signals": asdict(signals),
        "threshold": threshold,
        "mitigation": mitigation,
    }
    return [
        build_alert(
            severity=severity,
            category="burnout",
            title="Burnout risk detected",
            triggers=triggers,
            threshold=threshold,
            mitigation=mitigation,
            payload=payload,
        )
    ]


def _overcommitment_risk(signals: RiskSignals) -> list[AlertDraft]:
    triggers = []
    working_hours = signals.working_hours_minutes
    scheduled = signals.meeting_minutes + signals.focus_minutes
    meeting_threshold = (
        int(working_hours * OVERCOMMITMENT_MEETING_RATIO)
        if working_hours
        else OVERCOMMITMENT_ABSOLUTE_MEETING_MINUTES
    )
    if working_hours and scheduled > working_hours:
        triggers.append(f"Scheduled {scheduled}m > working hours {working_hours}m")
    if signals.priorities_count >= OVERCOMMITMENT_PRIORITIES:
        triggers.append(f"Priorities count {signals.priorities_count}")
    if signals.meeting_minutes >= meeting_threshold:
        triggers.append(f"Meeting load {signals.meeting_minutes}m")
    if not triggers:
        return []
    severity = "HIGH" if working_hours and scheduled > working_hours else "MEDIUM"
    threshold = (
        f"Scheduled minutes > working hours or priorities >= {OVERCOMMITMENT_PRIORITIES} "
        f"or meeting minutes >= {meeting_threshold}"
    )
    mitigation = "Reduce scope, drop optional objectives, and cap meeting load."
    payload = {
        "signals": asdict(signals),
        "threshold": threshold,
        "mitigation": mitigation,
    }
    return [
        build_alert(
            severity=severity,
            category="overcommitment",
            title="Overcommitment risk detected",
            triggers=triggers,
            threshold=threshold,
            mitigation=mitigation,
            payload=payload,
        )
    ]


def _faith_risk(signals: RiskSignals) -> list[AlertDraft]:
    if signals.missed_prayer_windows < 1:
        return []
    triggers = [f"Missed prayer windows {signals.missed_prayer_windows}"]
    threshold = "Missed prayer windows >= 1"
    mitigation = "Reinstate prayer windows with a buffer before meetings."
    payload = {
        "signals": asdict(signals),
        "threshold": threshold,
        "mitigation": mitigation,
    }
    return [
        build_alert(
            severity="MEDIUM",
            category="faith",
            title="Faith alignment risk detected",
            triggers=triggers,
            threshold=threshold,
            mitigation=mitigation,
            payload=payload,
        )
    ]


def _health_risk(signals: RiskSignals) -> list[AlertDraft]:
    triggers = []
    if signals.health_fatigue:
        triggers.append("Fatigue flag")
    if signals.health_pain:
        triggers.append("Pain flag")
    if not triggers:
        return []
    severity = "HIGH" if signals.health_fatigue and signals.health_pain else "MEDIUM"
    threshold = "Fatigue or pain flag present"
    mitigation = "Reduce training load and protect recovery windows."
    payload = {
        "signals": asdict(signals),
        "threshold": threshold,
        "mitigation": mitigation,
    }
    return [
        build_alert(
            severity=severity,
            category="health",
            title="Health risk detected",
            triggers=triggers,
            threshold=threshold,
            mitigation=mitigation,
            payload=payload,
        )
    ]


def _finance_risk(signals: RiskSignals) -> list[AlertDraft]:
    if not signals.finance_anomaly:
        return []
    triggers = ["Finance anomaly flag"]
    threshold = "Runway or burn-rate anomaly detected"
    mitigation = "Review runway assumptions and freeze discretionary spend."
    payload = {
        "signals": asdict(signals),
        "threshold": threshold,
        "mitigation": mitigation,
    }
    return [
        build_alert(
            severity="HIGH",
            category="finance",
            title="Finance risk detected",
            triggers=triggers,
            threshold=threshold,
            mitigation=mitigation,
            payload=payload,
        )
    ]
