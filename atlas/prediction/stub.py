from __future__ import annotations

from atlas.prediction.base import PredictionClient
from atlas.prediction.models import PredictionResult, PredictionSeed, derive_verdict


class StubPredictionClient(PredictionClient):
    """Deterministic, offline audience-reaction client for tests and no-backend runs."""

    def simulate(self, seed: PredictionSeed) -> PredictionResult:
        corpus = "\n".join(doc.content for doc in seed.documents)
        report = _render_report(seed, corpus)
        verdict, risk_score = derive_verdict(corpus)
        return PredictionResult(
            report_markdown=report,
            outline="Reaction overview; Sentiment; Key voices; Trajectory",
            verdict=verdict,
            risk_score=risk_score,
            trajectories=[
                "Early: a vocal minority reacts and frames the narrative.",
                "Later: sentiment settles toward the dominant framing above.",
            ],
            simulation_id="stub-sim",
            report_id="stub-report",
            raw={"engine": "stub", "documents": len(seed.documents)},
        )


def _render_report(seed: PredictionSeed, corpus: str) -> str:
    verdict, risk_score = derive_verdict(corpus)
    lines = [
        "# MiroFish Audience Reaction (stub)",
        "",
        f"**Prediction requirement:** {seed.requirement}",
        f"**Reaction risk:** {verdict} (score {risk_score:.2f})",
        f"**Seed documents:** {len(seed.documents)}",
        "",
        "## Summary",
        "Simulated agents surface a mix of support and pushback; the stub "
        "estimates reaction risk from backlash language in the seed material.",
    ]
    if seed.additional_context:
        lines += ["", "## Context", seed.additional_context]
    return "\n".join(lines)
