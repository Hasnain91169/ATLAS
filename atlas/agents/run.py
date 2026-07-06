from __future__ import annotations

from typing import Any

from atlas.agents.roles import AGENT_CONFIGS
from atlas.llm.base import LLMClient
from atlas.llm.openai import OpenAIClient


def run_agents(
    context: dict[str, Any],
    enable_llm: bool,
    llm: LLMClient | None = None,
    fail_open: bool = False,
) -> dict[str, str]:
    daily_brief = context.get("daily_brief_markdown", "No daily brief available.")
    tasks_summary = context.get("tasks_summary", "No tasks summary available.")
    alerts_summary = context.get("alerts_summary", "No alerts summary available.")

    outputs: dict[str, str] = {}
    if not enable_llm:
        for config in AGENT_CONFIGS:
            outputs[config.name] = "LLM disabled. Draft output unavailable."
        return outputs

    if llm is None:
        try:
            llm = OpenAIClient.from_env()
        except Exception as exc:
            if fail_open:
                return {config.name: f"LLM error: {exc}" for config in AGENT_CONFIGS}
            raise

    for config in AGENT_CONFIGS:
        prompt = config.prompt_template.format(
            daily_brief=daily_brief,
            tasks_summary=tasks_summary,
            alerts_summary=alerts_summary,
        )
        try:
            outputs[config.name] = llm.complete(prompt)
        except Exception as exc:
            if fail_open:
                outputs[config.name] = f"LLM error: {exc}"
            else:
                raise
    return outputs
