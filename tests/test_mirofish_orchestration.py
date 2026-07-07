import json

import pytest

from atlas.prediction.mirofish import MiroFishClient
from atlas.prediction.models import PredictionSeed, SeedDocument


class FakeResponse:
    def __init__(self, payload: dict):
        self._data = json.dumps(payload).encode("utf-8")
        self.status = 200

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def ok(data: dict) -> FakeResponse:
    """Wrap data in MiroFish's real {"success", "data"} envelope."""
    return FakeResponse({"success": True, "data": data})


class FakeBackend:
    """Routes MiroFish requests by path/method using the real response shapes."""

    def __init__(self):
        self.run_status_calls = 0
        self.seen_paths: list[str] = []
        self.ontology_content_type = None

    def __call__(self, req, timeout=None):
        path = req.full_url.replace("http://localhost:5001", "")
        self.seen_paths.append(path)

        if path == "/api/graph/ontology/generate":
            self.ontology_content_type = req.headers.get("Content-type")
            return ok({"project_id": "p1"})
        if path == "/api/graph/build":
            return ok({"task_id": "t-graph"})
        if path == "/api/graph/task/t-graph":
            # graph_id is nested under result, status "completed".
            return ok({"status": "completed", "result": {"graph_id": "g1"}})
        if path == "/api/simulation/create":
            return ok({"simulation_id": "s1", "status": "created"})
        if path == "/api/simulation/prepare":
            return ok({"task_id": "t-prep", "status": "preparing"})
        if path == "/api/simulation/prepare/status":
            return ok({"status": "ready", "progress": 100})  # prepare -> "ready"
        if path == "/api/simulation/start":
            body = json.loads(req.data.decode("utf-8"))
            assert body["max_rounds"] == 3
            assert body["platform"] == "reddit"
            return ok({"runner_status": "running"})
        if path == "/api/simulation/s1/run-status":
            self.run_status_calls += 1
            if self.run_status_calls < 2:
                return ok({"runner_status": "running", "current_round": 0, "total_rounds": 2})
            return ok({"runner_status": "completed", "current_round": 2, "total_rounds": 2})
        if path == "/api/report/generate":
            return ok({"report_id": "r1", "task_id": "t-rep", "status": "generating"})
        if path == "/api/report/generate/status":
            return ok({"status": "completed", "progress": 100})
        if path == "/api/report/r1":
            return ok(
                {
                    "report_id": "r1",
                    "outline": {"sections": ["Reaction", "Sentiment"]},
                    "markdown_content": (
                        "# Reaction\nbacklash outrage protest boycott anger criticism"
                    ),
                }
            )
        raise AssertionError(f"Unexpected {req.method} {path}")


def _client(**kw):
    return MiroFishClient(
        "http://localhost:5001", max_rounds=3, poll_interval=0, deadline=30, **kw
    )


def test_full_pipeline(monkeypatch):
    backend = FakeBackend()
    monkeypatch.setattr("atlas.prediction.mirofish.urlopen", backend)

    seed = PredictionSeed(
        requirement="How will people react?",
        documents=[SeedDocument(filename="msg.md", content="A bold announcement.")],
    )
    result = _client().simulate(seed)

    assert result.verdict == "HIGH"          # heuristic on backlash-heavy report
    assert result.simulation_id == "s1"
    assert result.report_id == "r1"
    assert "backlash" in result.report_markdown
    assert backend.run_status_calls >= 2     # polling actually looped
    assert "multipart/form-data" in backend.ontology_content_type


from atlas.llm.base import LLMClient


class FakeLLM(LLMClient):
    def __init__(self, response):
        self.response = response

    def complete(self, prompt):
        return self.response


def test_llm_classifies_report(monkeypatch):
    monkeypatch.setattr("atlas.prediction.mirofish.urlopen", FakeBackend())
    # Report is backlash-heavy (heuristic -> HIGH), but the LLM overrides to LOW.
    llm = FakeLLM('{"verdict":"LOW","risk_score":0.15}')
    result = _client(llm=llm).simulate(
        PredictionSeed(requirement="q", documents=[])
    )
    assert result.verdict == "LOW"
    assert result.risk_score == 0.15


def test_success_false_raises(monkeypatch):
    def fail(req, timeout=None):
        return FakeResponse({"success": False, "error": "ontology extraction failed"})

    monkeypatch.setattr("atlas.prediction.mirofish.urlopen", fail)
    with pytest.raises(RuntimeError, match="ontology extraction failed"):
        _client().simulate(PredictionSeed(requirement="q", documents=[]))


class ZeroAgentBackend(FakeBackend):
    """Prepare completes but yields no entities (seed too thin)."""

    def __call__(self, req, timeout=None):
        path = req.full_url.replace("http://localhost:5001", "")
        if path == "/api/simulation/prepare/status":
            return ok({"status": "completed", "progress": 100, "result": {"entities_count": 0}})
        return super().__call__(req, timeout)


def test_zero_agent_prepare_fails_clearly(monkeypatch):
    monkeypatch.setattr("atlas.prediction.mirofish.urlopen", ZeroAgentBackend())
    with pytest.raises(RuntimeError, match="0 agents"):
        _client().simulate(PredictionSeed(requirement="q", documents=[]))


def test_backend_unreachable_message(monkeypatch):
    from urllib.error import URLError

    def boom(req, timeout=None):
        raise URLError("Connection refused")

    monkeypatch.setattr("atlas.prediction.mirofish.urlopen", boom)
    with pytest.raises(RuntimeError, match="backend running"):
        _client().simulate(PredictionSeed(requirement="q", documents=[]))
