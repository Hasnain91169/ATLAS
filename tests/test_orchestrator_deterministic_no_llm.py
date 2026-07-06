from atlas.org.orchestrator import run_atlas_synthesis, run_department_heads


def test_orchestrator_no_llm_produces_no_approvals():
    context = {
        "daily_brief_markdown": "Brief",
        "tasks_summary": "Tasks",
        "alerts_summary": "Alerts",
        "tasks": [],
        "alerts": [],
    }
    reports = run_department_heads(context, enable_llm=False)
    synthesis = run_atlas_synthesis(context, reports)

    assert len(reports) == 4
    assert synthesis["approval_candidates"] == []
