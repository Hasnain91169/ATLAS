from __future__ import annotations

from atlas.llm.base import LLMClient
from atlas.prediction.models import Verdict, derive_verdict

_VALID: set[str] = {"LOW", "MEDIUM", "HIGH"}
_MAX_REPORT_CHARS = 6000

# Native structured-output schema (used by providers that support it, e.g. Anthropic).
_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
        "risk_score": {"type": "number"},
        "rationale": {"type": "string"},
    },
    "required": ["verdict", "risk_score"],
    "additionalProperties": False,
}


def assess_reaction(
    report_markdown: str, requirement: str, llm: LLMClient | None = None
) -> tuple[Verdict, float]:
    """Classify audience-reaction risk from a MiroFish report.

    Uses ``llm`` to read the prose report when available; falls back to the
    ``derive_verdict`` keyword heuristic when no client is given or the LLM
    output is unusable (fail-open, matching the org worker pattern).
    """
    if llm is None:
        return derive_verdict(report_markdown)
    try:
        return _classify_with_llm(report_markdown, requirement, llm)
    except Exception:
        return derive_verdict(report_markdown)


def _classify_with_llm(
    report_markdown: str, requirement: str, llm: LLMClient
) -> tuple[Verdict, float]:
    # Prefer native structured outputs; the base client falls back to complete()+parse.
    parsed = llm.complete_structured(
        _build_prompt(report_markdown, requirement), _VERDICT_SCHEMA
    )
    verdict = str(parsed.get("verdict", "")).upper()
    if verdict not in _VALID:
        raise ValueError(f"Invalid verdict: {verdict!r}")
    score = float(parsed.get("risk_score"))
    return verdict, min(1.0, max(0.0, score))  # type: ignore[return-value]


def _build_prompt(report_markdown: str, requirement: str) -> str:
    report = report_markdown[:_MAX_REPORT_CHARS]
    schema = '{"verdict":"LOW|MEDIUM|HIGH","risk_score":0.0,"rationale":"string"}'
    system = (
        "You are a communications risk analyst. A multi-agent simulation has "
        "produced a report on how an audience reacts to a proposed message. "
        "Classify the overall reaction risk: LOW (broadly accepted), MEDIUM "
        "(notable friction), or HIGH (backlash/reputational risk). risk_score "
        "is 0.0-1.0. Output JSON only, no markdown."
    )
    user = (
        f"Prediction requirement: {requirement}\n\n"
        f"Simulation report:\n{report}\n\n"
        f"Return JSON only in this schema:\n{schema}"
    )
    return f"SYSTEM:\n{system}\n\nUSER:\n{user}"
