from __future__ import annotations

import json
from pathlib import Path

from atlas.evals.models import VERDICTS, EvalExample

DEFAULT_DATASET = (
    Path(__file__).resolve().parents[2] / "evals" / "reaction_golden.jsonl"
)


def load_dataset(path: str | Path | None = None) -> list[EvalExample]:
    dataset_path = Path(path) if path else DEFAULT_DATASET
    examples: list[EvalExample] = []
    for lineno, raw in enumerate(
        dataset_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw.strip()
        if not line:
            continue
        obj = json.loads(line)
        expected = str(obj["expected"]).upper()
        if expected not in VERDICTS:
            raise ValueError(
                f"{dataset_path}:{lineno}: invalid expected verdict {expected!r}"
            )
        examples.append(EvalExample(text=str(obj["text"]), expected=expected))
    return examples
