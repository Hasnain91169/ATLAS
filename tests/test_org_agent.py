import json

from atlas.llm.base import LLMClient
from atlas.org.agent import run_department_heads_agent, run_head_agent
from atlas.org.trace import Tracer


class ScriptedLLM(LLMClient):
    """Returns a queued sequence of structured decisions."""

    def __init__(self, decisions):
        self._decisions = list(decisions)
        self.prompts = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return json.dumps(self._decisions.pop(0))

    # complete_structured falls back to complete()+json.loads via the base class.


def _context():
    return {
        "tasks": [{"id": "t1", "title": "Ship release", "list_id": "l1"}],
        "alerts": [{"severity": "HIGH", "title": "Burnout"}],
        "daily_brief_markdown": "# Brief\nBusy week.",
    }


def test_head_agent_uses_tool_then_finishes():
    llm = ScriptedLLM(
        [
            {"action": "use_tool", "tool": "query_alerts"},
            {
                "action": "final",
                "domain_summary": "Two risks found.",
                "key_risks": ["Burnout"],
                "recommendations": ["Protect focus time"],
            },
        ]
    )
    report = run_head_agent("Risk & Compliance", "risk", _context(), llm, max_steps=4)
    assert report.domain_summary == "Two risks found."
    assert report.key_risks == ["Burnout"]
    assert report.worker_trace[0]["tools_used"] == ["query_alerts"]
    assert report.worker_trace[0]["llm_calls"] == 2


def test_head_agent_forces_final_on_budget_exhaustion():
    # Never returns 'final' on its own — always asks for a tool.
    llm = ScriptedLLM([{"action": "use_tool", "tool": "query_tasks"}] * 10)
    report = run_head_agent("Operations", "ops", _context(), llm, max_steps=2)
    # 2 tool steps + 1 forced-final call = 3 calls
    assert report.worker_trace[0]["llm_calls"] == 3
    assert len(report.worker_trace[0]["tools_used"]) == 2
    # The forced-final prompt demands action='final'.
    assert "MUST set action='final'" in llm.prompts[-1]


def test_agent_path_traced():
    llm = ScriptedLLM(
        [{"action": "final", "domain_summary": "done"}] * 4
    )
    tracer = Tracer()
    reports = run_department_heads_agent(_context(), llm, max_steps=3, tracer=tracer)
    assert len(reports) == 4
    kinds = {span.kind for span in tracer.trace.spans}
    assert "head" in kinds and "agent_step" in kinds
    # every head produced at least one agent step
    assert sum(1 for s in tracer.trace.spans if s.kind == "agent_step") >= 4
