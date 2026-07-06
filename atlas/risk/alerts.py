from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AlertDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    severity: str
    category: str
    title: str
    message_markdown: str
    status: str = "DRAFT"
    tags: list[str] = Field(default_factory=list)
    payload: dict


def build_alert(
    *,
    severity: str,
    category: str,
    title: str,
    triggers: list[str],
    threshold: str,
    mitigation: str,
    payload: dict,
) -> AlertDraft:
    lines = [
        f"- Triggering signals: {', '.join(triggers)}",
        f"- Threshold crossed: {threshold}",
        f"- Recommended mitigation: {mitigation}",
    ]
    message_markdown = "\n".join(lines)
    tags = ["risk", category]
    return AlertDraft(
        severity=severity,
        category=category,
        title=title,
        message_markdown=message_markdown,
        tags=tags,
        payload=payload,
    )
