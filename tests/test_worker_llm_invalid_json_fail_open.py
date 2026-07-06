from atlas.org.roles import TaskAnalystWorker


class FakeLLM:
    def complete(self, prompt: str) -> str:
        return "not json"


def test_worker_llm_invalid_json_fail_open():
    worker = TaskAnalystWorker()
    context = {"tasks": [{"id": "task-1", "title": "Finish report"}]}
    result = worker.run(context, enable_llm=True, llm=FakeLLM(), head_name="Operations")

    assert result.output == "LLM output invalid JSON"
    assert result.confidence == 0.2
    assert result.uncertainties
