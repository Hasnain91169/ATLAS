import json

from atlas.evals.dataset import load_dataset
from atlas.evals.models import EvalExample
from atlas.evals.report import render_markdown
from atlas.evals.runner import run_eval
from atlas.llm.base import LLMClient
from atlas.storage.sqlite import connect, init_db, insert_eval_run


class ConstLLM(LLMClient):
    """Always classifies HIGH — deterministic for eval tests."""

    def complete(self, prompt: str) -> str:
        return '{"verdict":"HIGH","risk_score":0.9}'


def _examples():
    return [
        EvalExample("outrage backlash boycott protest anger criticism", "HIGH"),
        EvalExample("a calm and welcome update", "LOW"),
        EvalExample("some concern and mild criticism", "MEDIUM"),
    ]


def test_golden_dataset_loads_and_is_valid():
    examples = load_dataset()
    assert len(examples) >= 25
    assert all(e.expected in {"LOW", "MEDIUM", "HIGH"} for e in examples)
    assert all(e.text for e in examples)


def test_run_eval_heuristic_only():
    report = run_eval(_examples())
    assert report.n == 3
    assert [j.name for j in report.judges] == ["heuristic"]
    assert report.agreement is None
    heuristic = report.judges[0]
    # confusion counts sum to n
    assert sum(heuristic.confusion.values()) == 3
    assert 0.0 <= heuristic.accuracy <= 1.0


def test_run_eval_with_llm_agreement_and_accuracy():
    report = run_eval(_examples(), llm=ConstLLM())
    names = [j.name for j in report.judges]
    assert names == ["heuristic", "llm"]
    llm = next(j for j in report.judges if j.name == "llm")
    # ConstLLM says HIGH for all 3; only the first example is truly HIGH.
    assert llm.correct == 1
    assert llm.accuracy == 1 / 3
    assert report.agreement is not None


def test_render_markdown_contains_tables():
    md = render_markdown(run_eval(_examples(), llm=ConstLLM()))
    assert "Accuracy" in md
    assert "Confusion" in md
    assert "agreement" in md.lower()


def test_insert_eval_run_persists(tmp_path):
    db_path = tmp_path / "atlas.db"
    conn = connect(db_path)
    try:
        init_db(conn)
        report = run_eval(_examples(), llm=ConstLLM())
        run_id = insert_eval_run(conn, report)
        row = conn.execute(
            "SELECT dataset, n, heuristic_accuracy, llm_accuracy, agreement, metrics_json "
            "FROM eval_run WHERE id = ?",
            (run_id,),
        ).fetchone()
        assert row["n"] == 3
        assert row["llm_accuracy"] is not None
        metrics = json.loads(row["metrics_json"])
        assert "judges" in metrics and "llm" in metrics["judges"]
    finally:
        conn.close()


def test_cli_evals_run(tmp_path, capsys):
    from atlas.cli import run_evals_run

    exit_code = run_evals_run(str(tmp_path / "atlas.db"), None, 10, enable_llm=False)
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Reaction classifier eval" in out
    assert "heuristic" in out
