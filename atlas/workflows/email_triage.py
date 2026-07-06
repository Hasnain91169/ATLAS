from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from atlas.risk.alerts import AlertDraft, build_alert

URGENT_KEYWORDS = ["urgent", "asap", "immediately", "today", "deadline", "critical"]
IMPORTANT_KEYWORDS = ["review", "approve", "decision", "proposal", "contract", "budget"]
DELEGATE_KEYWORDS = ["schedule", "meeting", "follow up", "coordinate", "please handle"]
IGNORE_KEYWORDS = ["unsubscribe", "newsletter", "promo", "marketing"]

LEGAL_KEYWORDS = ["legal", "lawsuit", "compliance", "regulatory", "contract breach"]
REPUTATION_KEYWORDS = ["press", "reputation", "public", "media", "scandal"]
EMOTIONAL_KEYWORDS = ["angry", "upset", "harassment", "threat", "complaint"]


@dataclass(frozen=True)
class TriageMessage:
    message_id: str
    sender: str
    subject: str
    body: str


@dataclass(frozen=True)
class TriageItem:
    message_id: str
    sender: str
    subject: str
    category: str
    rationale: str


@dataclass(frozen=True)
class DraftReply:
    message_id: str
    suggestion: str


@dataclass(frozen=True)
class TriageReport:
    created_at: datetime
    markdown: str
    payload: dict
    tags: list[str]
    alerts: list[AlertDraft]


def _normalize(text: str) -> str:
    return text.lower()


def _contains_any(text: str, keywords: list[str]) -> list[str]:
    found = []
    for word in keywords:
        if word in text:
            found.append(word)
    return found


def _classify_message(message: TriageMessage) -> tuple[str, str]:
    text = _normalize(f"{message.subject} {message.body}")
    urgent_hits = _contains_any(text, URGENT_KEYWORDS)
    ignore_hits = _contains_any(text, IGNORE_KEYWORDS)
    important_hits = _contains_any(text, IMPORTANT_KEYWORDS)
    delegate_hits = _contains_any(text, DELEGATE_KEYWORDS)

    if urgent_hits:
        return "Urgent", f"Matched urgent keywords: {', '.join(urgent_hits)}"
    if ignore_hits:
        return "Ignore", f"Matched ignore keywords: {', '.join(ignore_hits)}"
    if important_hits:
        return "Important", f"Matched important keywords: {', '.join(important_hits)}"
    if delegate_hits:
        return "Delegate", f"Matched delegate keywords: {', '.join(delegate_hits)}"
    return "Important", "Defaulted to Important due to no ignore/urgent match."


def _detect_risk_alerts(message: TriageMessage) -> list[AlertDraft]:
    text = _normalize(f"{message.subject} {message.body}")
    alerts: list[AlertDraft] = []

    legal_hits = _contains_any(text, LEGAL_KEYWORDS)
    if legal_hits:
        alerts.append(
            build_alert(
                severity="HIGH",
                category="legal",
                title=f"Legal risk flagged in message {message.message_id}",
                triggers=[f"Keywords: {', '.join(legal_hits)}"],
                threshold="Legal risk keywords present",
                mitigation="Escalate to Risk & Compliance before responding.",
                payload={"message_id": message.message_id, "keywords": legal_hits},
            )
        )

    reputation_hits = _contains_any(text, REPUTATION_KEYWORDS)
    if reputation_hits:
        alerts.append(
            build_alert(
                severity="HIGH",
                category="reputation",
                title=f"Reputation risk flagged in message {message.message_id}",
                triggers=[f"Keywords: {', '.join(reputation_hits)}"],
                threshold="Reputation risk keywords present",
                mitigation="Draft response with cautious tone and review externally.",
                payload={"message_id": message.message_id, "keywords": reputation_hits},
            )
        )

    emotional_hits = _contains_any(text, EMOTIONAL_KEYWORDS)
    if emotional_hits:
        alerts.append(
            build_alert(
                severity="MEDIUM",
                category="emotional",
                title=f"Emotionally loaded content in message {message.message_id}",
                triggers=[f"Keywords: {', '.join(emotional_hits)}"],
                threshold="Emotionally loaded keywords present",
                mitigation="Slow response, acknowledge emotions, avoid escalation.",
                payload={"message_id": message.message_id, "keywords": emotional_hits},
            )
        )

    return alerts


def load_messages(path: str | Path) -> list[TriageMessage]:
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if input_path.suffix.lower() in {".yaml", ".yml"}:
        data: Any = yaml.safe_load(input_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("YAML input must be a list of messages.")
        return [
            TriageMessage(
                message_id=str(item.get("id", idx + 1)),
                sender=str(item.get("sender", "unknown")),
                subject=str(item.get("subject", "")),
                body=str(item.get("body", "")),
            )
            for idx, item in enumerate(data)
        ]

    if input_path.suffix.lower() == ".jsonl":
        messages: list[TriageMessage] = []
        for idx, line in enumerate(input_path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            item = json.loads(line)
            messages.append(
                TriageMessage(
                    message_id=str(item.get("id", idx + 1)),
                    sender=str(item.get("sender", "unknown")),
                    subject=str(item.get("subject", "")),
                    body=str(item.get("body", "")),
                )
            )
        return messages

    raise ValueError("Unsupported input format. Use .yaml, .yml, or .jsonl.")


def _render_markdown(
    items: list[TriageItem],
    draft_replies: list[DraftReply],
    alerts: list[AlertDraft],
) -> str:
    lines: list[str] = []
    lines.append("# Email Triage Report")
    lines.append("")
    for category in ["Urgent", "Important", "Delegate", "Ignore"]:
        lines.append(f"## {category}")
        category_items = [item for item in items if item.category == category]
        if not category_items:
            lines.append("- None")
        for item in category_items:
            lines.append(
                f"- {item.subject} (from {item.sender}) "
                f"[id: {item.message_id}] — {item.rationale}"
            )
        lines.append("")

    lines.append("## Draft Reply Suggestions")
    if draft_replies:
        for reply in draft_replies:
            lines.append(f"- [id: {reply.message_id}] {reply.suggestion}")
    else:
        lines.append("- None")
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


def generate_triage_report(messages: list[TriageMessage]) -> TriageReport:
    items: list[TriageItem] = []
    draft_replies: list[DraftReply] = []
    alerts: list[AlertDraft] = []
    for message in messages:
        category, rationale = _classify_message(message)
        items.append(
            TriageItem(
                message_id=message.message_id,
                sender=message.sender,
                subject=message.subject,
                category=category,
                rationale=rationale,
            )
        )
        if category in {"Urgent", "Important"}:
            draft_replies.append(
                DraftReply(
                    message_id=message.message_id,
                    suggestion="Draft a response acknowledging receipt and requesting needed context.",
                )
            )
        alerts.extend(_detect_risk_alerts(message))

    tags = ["triage"]
    categories = {item.category.lower() for item in items}
    tags.extend(sorted(categories))

    payload = {
        "items": [asdict(item) for item in items],
        "draft_replies": [asdict(reply) for reply in draft_replies],
    }
    markdown = _render_markdown(items, draft_replies, alerts)
    return TriageReport(
        created_at=datetime.now(timezone.utc),
        markdown=markdown,
        payload=payload,
        tags=tags,
        alerts=alerts,
    )


def triage_payload_json(report: TriageReport) -> str:
    return json.dumps(report.payload, sort_keys=True)
