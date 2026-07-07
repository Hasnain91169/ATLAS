from __future__ import annotations

from dataclasses import dataclass, field

VERDICTS = ["LOW", "MEDIUM", "HIGH"]


@dataclass(frozen=True)
class EvalExample:
    text: str
    expected: str


@dataclass
class JudgeMetrics:
    name: str
    n: int = 0
    correct: int = 0
    total_latency: float = 0.0
    # (expected, predicted) -> count
    confusion: dict[tuple[str, str], int] = field(
        default_factory=lambda: {(e, p): 0 for e in VERDICTS for p in VERDICTS}
    )

    @property
    def accuracy(self) -> float:
        return self.correct / self.n if self.n else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return 1000.0 * self.total_latency / self.n if self.n else 0.0

    def record(self, expected: str, predicted: str) -> None:
        self.n += 1
        if expected == predicted:
            self.correct += 1
        if (expected, predicted) in self.confusion:
            self.confusion[(expected, predicted)] += 1


@dataclass
class EvalReport:
    dataset: str
    n: int
    judges: list[JudgeMetrics]
    agreement: float | None = None  # heuristic vs LLM verdict agreement rate
