"""Interactive offline tour of ATLAS — https://github.com/Hasnain91169/ATLAS

Everything here runs in ATLAS's deterministic **stub / offline mode**: no API
keys, no external services, no per-request cost. The audience simulation is the
built-in keyword-heuristic stub (not a live MiroFish run), and the org trace
below uses a scripted offline model (no real API calls) purely to illustrate the
cost/latency tracing. See the repo for the real, LLM-backed paths.
"""

from __future__ import annotations

import streamlit as st

from atlas.evals.dataset import load_dataset
from atlas.evals.report import render_markdown as render_eval
from atlas.evals.runner import run_eval
from atlas.llm.base import LLMClient, LLMUsage
from atlas.org.orchestrator import run_atlas_synthesis, run_department_heads
from atlas.org.trace import Tracer, render_trace
from atlas.prediction.audience import build_seed
from atlas.prediction.models import SeedDocument
from atlas.prediction.stub import StubPredictionClient

st.set_page_config(page_title="ATLAS — offline demo", page_icon="🧭", layout="wide")


class DemoLLM(LLMClient):
    """Scripted offline stand-in so the trace/cost view is populated (no API calls)."""

    def complete(self, prompt: str) -> str:
        self.last_usage = LLMUsage(input_tokens=180, output_tokens=60, cost_usd=0.0012)
        if "department head" in prompt:
            return (
                '{"domain_summary":"Synthesized worker findings.",'
                '"key_risks":["Meeting load is high this week"],'
                '"recommendations_for_atlas":["Protect a 2h focus block","Defer optional scope"],'
                '"proposed_actions":[],"confidence":0.7,"uncertainties":[]}'
            )
        return (
            '{"summary":"Reviewed the current context.","findings":[],'
            '"risks":["Meeting load is high"],"recommendations":["Protect a focus block"],'
            '"proposed_actions":[],"confidence":0.7,"uncertainties":[],"missing_inputs":[]}'
        )


DEMO_CONTEXT = {
    "tasks": [
        {"id": "t1", "title": "Ship v0.2 release", "due": "2026-07-10", "list_id": "l1", "status": "needsAction"},
        {"id": "t2", "title": "Review Q3 budget", "due": None, "list_id": "l1", "status": "needsAction"},
    ],
    "alerts": [
        {"severity": "HIGH", "title": "Burnout risk detected"},
        {"severity": "MEDIUM", "title": "Overcommitment risk detected"},
    ],
    "daily_brief_markdown": "# Daily Brief\n- 5 meetings, 90m focus time\n- 2 high-priority tasks",
}

st.title("🧭 ATLAS — a multi-agent personal operating company")
st.caption(
    "Interactive **offline** tour. No API keys, no external services, no cost. "
    "[Source on GitHub](https://github.com/Hasnain91169/ATLAS)"
)

tab_predict, tab_evals, tab_org = st.tabs(
    ["🔮 Audience prediction", "📊 Eval harness", "🏢 Org run + trace"]
)

with tab_predict:
    st.subheader("Rehearse how an audience reacts to a message")
    st.caption(
        "Offline stub of the MiroFish audience-reaction pipeline — the verdict comes "
        "from a keyword heuristic, not a live simulation."
    )
    requirement = st.text_input(
        "Prediction requirement", "How will staff react to this reorg?"
    )
    message = st.text_area(
        "Message / announcement",
        "We are merging Platform Engineering and Infrastructure into one Core Systems "
        "group. No layoffs and no comp changes, but 18 management roles are consolidated "
        "and several teams get a new reporting line.",
        height=160,
    )
    if st.button("Predict reaction", type="primary"):
        seed = build_seed(requirement, [SeedDocument(filename="message.md", content=message)])
        result = StubPredictionClient().simulate(seed)
        color = {"LOW": "green", "MEDIUM": "orange", "HIGH": "red"}[result.verdict]
        st.markdown(
            f"### Reaction risk: :{color}[{result.verdict}]  ·  score {result.risk_score:.2f}"
        )
        st.markdown(result.report_markdown)
        with st.expander("Predicted trajectories"):
            for line in result.trajectories:
                st.markdown(f"- {line}")

with tab_evals:
    st.subheader("Evaluate the reaction-verdict classifiers")
    st.caption(
        "Scores the keyword heuristic against a 30-example labeled golden set. "
        "This is how we *know* the heuristic underperforms an LLM judge, rather than assume it."
    )
    if st.button("Run eval", type="primary"):
        report = run_eval(load_dataset())
        heuristic = report.judges[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Examples", report.n)
        c2.metric("Heuristic accuracy", f"{heuristic.accuracy:.0%}")
        c3.metric("HIGH cases caught", f"{heuristic.confusion[('HIGH', 'HIGH')]}/10")
        st.markdown(render_eval(report))

with tab_org:
    st.subheader("Hierarchical org run with cost/latency tracing")
    st.caption(
        "Workers → department heads → orchestrator synthesis. The trace uses a "
        "**scripted offline model** (no real API calls); token/cost figures are illustrative."
    )
    if st.button("Run org pipeline", type="primary"):
        tracer = Tracer()
        reports = run_department_heads(
            DEMO_CONTEXT, enable_llm=True, llm=DemoLLM(), tracer=tracer
        )
        synthesis = run_atlas_synthesis(DEMO_CONTEXT, reports)
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### Atlas synthesis")
            st.markdown("**What mattered**")
            for item in synthesis["what_mattered"]:
                st.markdown(f"- {item}")
            st.markdown("**What happens next**")
            for item in synthesis["what_happens_next"][:6]:
                st.markdown(f"- {item}")
        with col_b:
            t = tracer.trace
            st.markdown("#### Trace")
            m1, m2, m3 = st.columns(3)
            m1.metric("LLM calls", t.llm_calls)
            m2.metric("Tokens", t.total_tokens)
            m3.metric("Cost", f"${t.total_cost_usd:.4f}")
            st.code(render_trace(t.trace), language="text")
