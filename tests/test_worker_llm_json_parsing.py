import json

from atlas.org.roles import TaskAnalystWorker


class FakeLLM:
    def complete(self, prompt: str) -> str:
        return json.dumps(
            {
                "summary": "Review top tasks.",
                "findings": ["Two tasks due soon."],
                "risks": ["Overloaded schedule."],
                "recommendations": ["Finish the highest-priority task."],
                "proposed_actions": [
                    {
                        "action_type": "task_complete",
                        "payload": {"list_id": "list-1", "task_id": "task-1"},
                        "reason": "Quick win.",
                    }
                ],
                "confidence": 0.8,
                "uncertainties": ["Task priorities may be stale."],
                "missing_inputs": [],
            }
        )


def test_worker_llm_json_parsing():
    worker = TaskAnalystWorker()
    context = {"tasks": [{"id": "task-1", "title": "Finish report"}]}
    result = worker.run(context, enable_llm=True, llm=FakeLLM(), head_name="Operations")

    assert result.llm_output is not None
    assert result.output == "Review top tasks."
    assert result.confidence == 0.8
