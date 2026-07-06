from atlas.agents.run import run_agents


class FakeLLM:
    def complete(self, prompt: str) -> str:
        return "FAKE OUTPUT"


def test_agents_placeholder_when_disabled():
    outputs = run_agents({}, enable_llm=False)
    assert all("LLM disabled" in value for value in outputs.values())


def test_agents_with_fake_llm():
    outputs = run_agents(
        {"daily_brief_markdown": "Brief", "tasks_summary": "Tasks", "alerts_summary": "Alerts"},
        enable_llm=True,
        llm=FakeLLM(),
    )
    assert all(value == "FAKE OUTPUT" for value in outputs.values())
