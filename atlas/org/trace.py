from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class Span:
    name: str
    kind: str  # "worker" | "head" | "synthesis" | "agent_step"
    parent: str | None = None
    duration_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    llm: bool = False
    note: str = ""

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class SpanHandle:
    """Handed to the code inside a span so it can attach LLM usage / a note."""

    def __init__(self) -> None:
        self.usage = None  # atlas.llm.base.LLMUsage | None
        self.note = ""


@dataclass
class Trace:
    run_id: str
    spans: list[Span] = field(default_factory=list)

    @property
    def total_cost_usd(self) -> float:
        return sum(span.cost_usd for span in self.spans)

    @property
    def total_tokens(self) -> int:
        return sum(span.tokens for span in self.spans)

    @property
    def llm_calls(self) -> int:
        return sum(1 for span in self.spans if span.llm)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "total_cost_usd": self.total_cost_usd,
            "total_tokens": self.total_tokens,
            "llm_calls": self.llm_calls,
            "spans": [span.__dict__ for span in self.spans],
        }


class Tracer:
    def __init__(self, run_id: str | None = None) -> None:
        self.trace = Trace(run_id=run_id or uuid.uuid4().hex[:12])

    @contextmanager
    def span(self, name: str, kind: str, parent: str | None = None) -> Iterator[SpanHandle]:
        handle = SpanHandle()
        start = time.perf_counter()
        try:
            yield handle
        finally:
            usage = handle.usage
            self.trace.spans.append(
                Span(
                    name=name,
                    kind=kind,
                    parent=parent,
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                    input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
                    output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
                    cost_usd=getattr(usage, "cost_usd", 0.0) if usage else 0.0,
                    llm=usage is not None,
                    note=handle.note,
                )
            )


@contextmanager
def maybe_span(
    tracer: Tracer | None, name: str, kind: str, parent: str | None = None
) -> Iterator[SpanHandle | None]:
    """Span when tracing is on, no-op otherwise — keeps call sites clean."""
    if tracer is None:
        yield None
    else:
        with tracer.span(name, kind, parent=parent) as handle:
            yield handle


def render_trace(trace: Trace) -> str:
    """Pretty-print the span tree for `atlas trace show`."""
    lines = [
        f"# Org run trace {trace.run_id}",
        "",
        f"LLM calls: {trace.llm_calls}   Tokens: {trace.total_tokens}   "
        f"Cost: ${trace.total_cost_usd:.4f}",
        "",
    ]
    roots = [s for s in trace.spans if s.parent is None]
    children: dict[str, list[Span]] = {}
    for span in trace.spans:
        if span.parent is not None:
            children.setdefault(span.parent, []).append(span)

    def emit(span: Span, depth: int) -> None:
        indent = "  " * depth
        cost = f" ${span.cost_usd:.4f}" if span.cost_usd else ""
        toks = f" {span.tokens}tok" if span.tokens else ""
        tag = "[llm]" if span.llm else "     "
        note = f" — {span.note}" if span.note else ""
        lines.append(
            f"{indent}{tag} {span.name} ({span.kind}) {span.duration_ms:.0f}ms"
            f"{toks}{cost}{note}"
        )
        for child in children.get(span.name, []):
            emit(child, depth + 1)

    for root in roots:
        emit(root, 0)
    return "\n".join(lines)
