from __future__ import annotations

import time
from collections.abc import Iterable

from atlas.evals.models import EvalExample, EvalReport, JudgeMetrics
from atlas.llm.base import LLMClient
from atlas.prediction.assess import assess_reaction
from atlas.prediction.models import derive_verdict

REQUIREMENT = "How will the audience react to this?"


def run_eval(
    examples: Iterable[EvalExample],
    llm: LLMClient | None = None,
    dataset: str = "reaction_golden",
) -> EvalReport:
    """Score the heuristic and (optionally) LLM judge against labeled examples.

    The heuristic is always evaluated; when ``llm`` is provided the LLM-as-judge
    is evaluated too and its agreement with the heuristic is reported.
    """
    examples = list(examples)
    heuristic = JudgeMetrics("heuristic")
    judges = [heuristic]
    llm_metrics = JudgeMetrics("llm") if llm is not None else None
    if llm_metrics is not None:
        judges.append(llm_metrics)

    agreements = 0
    for example in examples:
        start = time.perf_counter()
        h_verdict = derive_verdict(example.text)[0]
        heuristic.total_latency += time.perf_counter() - start
        heuristic.record(example.expected, h_verdict)

        if llm_metrics is not None:
            start = time.perf_counter()
            l_verdict = assess_reaction(example.text, REQUIREMENT, llm)[0]
            llm_metrics.total_latency += time.perf_counter() - start
            llm_metrics.record(example.expected, l_verdict)
            if l_verdict == h_verdict:
                agreements += 1

    agreement = (
        agreements / len(examples) if llm_metrics is not None and examples else None
    )
    return EvalReport(
        dataset=dataset, n=len(examples), judges=judges, agreement=agreement
    )
