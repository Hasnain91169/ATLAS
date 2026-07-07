from atlas.llm.base import LLMClient, LLMUsage
from atlas.org.orchestrator import run_department_heads
from atlas.org.trace import Span, Trace, Tracer, render_trace
from atlas.storage.sqlite import connect, get_trace, init_db, insert_trace


class UsageLLM(LLMClient):
    """Returns valid worker/head JSON and reports token usage per call."""

    def complete(self, prompt: str) -> str:
        self.last_usage = LLMUsage(input_tokens=100, output_tokens=50, cost_usd=0.001)
        return (
            '{"summary":"s","findings":[],"risks":["r"],"recommendations":["do x"],'
            '"proposed_actions":[],"confidence":0.7,"uncertainties":[],"missing_inputs":[]}'
        )


def _context():
    return {
        "tasks": [{"id": "t1", "title": "x", "list_id": "l1"}],
        "alerts": [],
        "daily_brief_markdown": "# brief",
    }


def test_tracer_records_worker_and_head_spans():
    tracer = Tracer()
    run_department_heads(_context(), enable_llm=True, llm=UsageLLM(), tracer=tracer)
    trace = tracer.trace
    kinds = {span.kind for span in trace.spans}
    assert {"head", "worker", "synthesis"} <= kinds
    assert trace.llm_calls > 0
    assert trace.total_tokens > 0
    assert trace.total_cost_usd > 0
    # workers hang under their head in the tree
    worker = next(s for s in trace.spans if s.kind == "worker")
    assert worker.parent in {"Operations", "Risk & Compliance", "Finance", "Learning"}


def test_no_tracer_is_noop():
    # Should not raise and returns reports as before.
    reports = run_department_heads(_context(), enable_llm=True, llm=UsageLLM())
    assert len(reports) == 4


def test_trace_storage_round_trip(tmp_path):
    trace = Trace(
        run_id="abc123",
        spans=[Span("Operations", "head", None, 12.0),
               Span("TaskAnalyst", "worker", "Operations", 5.0, 100, 50, 0.001, True)],
    )
    conn = connect(tmp_path / "atlas.db")
    try:
        init_db(conn)
        insert_trace(conn, trace)
        record = get_trace(conn, "abc123")
    finally:
        conn.close()
    assert record["run_id"] == "abc123"
    assert record["llm_calls"] == 1
    assert record["trace"]["total_tokens"] == 150


def test_render_trace_tree():
    trace = Trace(
        run_id="r1",
        spans=[Span("Operations", "head", None, 10.0),
               Span("TaskAnalyst", "worker", "Operations", 5.0, 100, 50, 0.001, True)],
    )
    out = render_trace(trace)
    assert "Operations (head)" in out
    assert "TaskAnalyst (worker)" in out
    assert "[llm]" in out
