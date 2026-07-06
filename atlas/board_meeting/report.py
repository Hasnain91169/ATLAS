from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from atlas.org.orchestrator import build_context, run_atlas_synthesis, run_department_heads
from atlas.storage.sqlite import connect, default_db_path, init_db


def generate_board_report(
    db_path: str | Path | None,
    enable_llm: bool,
    verbose: bool = False,
) -> str:
    resolved_db_path = (
        Path(db_path).expanduser().resolve() if db_path else default_db_path()
    )
    conn = connect(resolved_db_path)
    try:
        init_db(conn)
        context = build_context(conn)
    finally:
        conn.close()

    head_reports = run_department_heads(context, enable_llm=enable_llm)
    synthesis = run_atlas_synthesis(context, head_reports)

    today = datetime.now(timezone.utc).date().isoformat()
    lines: list[str] = []
    lines.append(f"# Board Meeting Report - {today}")
    lines.append("")
    lines.append("## Atlas Synthesis")
    lines.append("### What mattered")
    for item in synthesis["what_mattered"]:
        lines.append(f"- {item}")
    lines.append("### What happens next")
    for item in synthesis["what_happens_next"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Department Head Drafts (AI)")

    order = ["Operations", "Risk & Compliance", "Finance", "Learning"]
    head_map = {report.head_name: report for report in head_reports}
    for name in order:
        report = head_map.get(name)
        if not report:
            continue
        lines.append(f"### {report.head_name}")
        lines.append(f"Summary: {report.domain_summary}")
        lines.append("Key Risks:")
        if report.key_risks:
            for risk in report.key_risks:
                lines.append(f"- {risk}")
        else:
            lines.append("- None")
        lines.append("Recommendations:")
        if report.recommendations_for_atlas:
            for rec in report.recommendations_for_atlas:
                lines.append(f"- {rec}")
        else:
            lines.append("- None")
        if report.uncertainties:
            lines.append("Uncertainties:")
            for item in report.uncertainties:
                lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines)
