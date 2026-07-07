from __future__ import annotations

from atlas.evals.models import VERDICTS, EvalReport


def render_markdown(report: EvalReport) -> str:
    lines: list[str] = [
        f"# Reaction classifier eval - `{report.dataset}` (n={report.n})",
        "",
        "| Judge | Accuracy | Correct | Avg latency |",
        "| --- | --- | --- | --- |",
    ]
    for judge in report.judges:
        lines.append(
            f"| {judge.name} | {judge.accuracy:.1%} | {judge.correct}/{judge.n} "
            f"| {judge.avg_latency_ms:.1f} ms |"
        )
    if report.agreement is not None:
        lines += ["", f"**Heuristic vs LLM agreement:** {report.agreement:.1%}"]

    for judge in report.judges:
        lines += ["", f"## Confusion - {judge.name}", "", _confusion_table(judge)]
    return "\n".join(lines)


def _confusion_table(judge) -> str:
    header = "| expected \\ predicted | " + " | ".join(VERDICTS) + " |"
    sep = "| --- " * (len(VERDICTS) + 1) + "|"
    rows = [header, sep]
    for expected in VERDICTS:
        cells = " | ".join(str(judge.confusion[(expected, p)]) for p in VERDICTS)
        rows.append(f"| **{expected}** | {cells} |")
    return "\n".join(rows)
