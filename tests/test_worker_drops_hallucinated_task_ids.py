import json

from atlas.org.roles import TaskAnalystWorker


class FakeLLM:
    def complete(self, prompt: str) -> str:
        return json.dumps(
            {
                "summary": "Complete a task.",
                "findings": [],
                "risks": [],
                "recommendations": ["Complete the top task."],
                "proposed_actions": [
                    {
                        "action_type": "task_complete",
                        "payload": {"list_id": "list-1", "task_id": "task-x"},
                        "reason": "Quick win.",
                    }
                ],
                "confidence": 0.7,
                "uncertainties": [],
                "missing_inputs": [],
            }
        )


def test_worker_drops_hallucinated_task_ids():
    worker = TaskAnalystWorker()
    context = {
        "tasks": [{"id": "task-1", "title": "Finish report", "list_id": "list-1"}]
    }
    result = worker.run(context, enable_llm=True, llm=FakeLLM(), head_name="Operations")

    assert result.llm_output is not None
    assert result.llm_output.proposed_actions
    assert result.llm_output.proposed_actions[0]["action_type"] == "request_more_info"
    assert any("Dropped task_complete" in item for item in result.uncertainties)
