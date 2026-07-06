import json

from atlas.org.orchestrator import run_atlas_synthesis, run_department_heads


class FakeLLM:
    def complete(self, prompt: str) -> str:
        return json.dumps(
            {
                "summary": "Complete one task.",
                "findings": [],
                "risks": [],
                "recommendations": ["Complete a task."],
                "proposed_actions": [
                    {
                        "action_type": "task_complete",
                        "payload": {"list_id": "list-1", "task_id": "task-1"},
                        "reason": "Clears a quick win.",
                    }
                ],
                "confidence": 0.7,
                "uncertainties": [],
                "missing_inputs": [],
            }
        )


def test_orchestrator_llm_actions_parsing():
    context = {
        "daily_brief_markdown": "Brief",
        "tasks_summary": "Tasks",
        "alerts_summary": "Alerts",
        "tasks": [{"id": "task-1", "title": "Finish report", "list_id": "list-1"}],
        "alerts": [],
    }
    reports = run_department_heads(context, enable_llm=True, llm=FakeLLM())
    synthesis = run_atlas_synthesis(context, reports)

    assert synthesis["approval_candidates"]
    assert any(
        candidate["action_type"] == "task_complete"
        for candidate in synthesis["approval_candidates"]
    )
