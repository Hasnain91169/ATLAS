import json

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


class FakeBackend:
    """Routes MiroFish requests by path/method and drives one poll loop."""

    def __init__(self):
        self.run_status_calls = 0
        self.seen_paths: list[str] = []
        self.ontology_content_type = None

    def __call__(self, req, timeout=None):
        path = req.full_url.replace("http://localhost:5001", "")
        self.seen_paths.append(path)
        method = req.method

        if path == "/api/graph/ontology/generate":
            self.ontology_content_type = req.headers.get("Content-type")
            return FakeResponse({"project_id": "p1"})
        if path == "/api/graph/build":
            return FakeResponse({"task_id": "t-graph"})
        if path == "/api/graph/task/t-graph":
            return FakeResponse({"status": "completed", "graph_id": "g1"})
        if path == "/api/simulation/create":
            return FakeResponse({"simulation_id": "s1"})
        if path == "/api/simulation/prepare":
            return FakeResponse({"task_id": "t-prep"})
        if path == "/api/simulation/prepare/status":
            return FakeResponse({"status": "completed"})
        if path == "/api/simulation/start":
            body = json.loads(req.data.decode("utf-8"))
            assert body["max_rounds"] == 3
            assert body["platform"] == "reddit"
            return FakeResponse({"status": "running", "pid": 42})
        if path == "/api/simulation/s1/run-status":
            self.run_status_calls += 1
            if self.run_status_calls < 2:
                return FakeResponse({"current_round": 0, "total_rounds": 2})
            return FakeResponse({"current_round": 2, "total_rounds": 2})
        if path == "/api/report/generate":
            return FakeResponse({"report_id": "r1", "task_id": "t-rep"})
        if path == "/api/report/generate/status":
            return FakeResponse({"status": "completed"})
        if path == "/api/report/r1":
            return FakeResponse(
                {
                    "report_id": "r1",
                    "outline": "Reaction; Sentiment",
                    "markdown_content": (
                        "# Reaction\nbacklash outrage protest boycott anger criticism"
                    ),
                }
            )
        raise AssertionError(f"Unexpected {method} {path}")


def test_full_pipeline(monkeypatch):
    backend = FakeBackend()
    monkeypatch.setattr("atlas.prediction.mirofish.urlopen", backend)

    client = MiroFishClient(
        "http://localhost:5001", max_rounds=3, poll_interval=0, deadline=30
    )
    seed = PredictionSeed(
        requirement="How will people react?",
        documents=[SeedDocument(filename="msg.md", content="A bold announcement.")],
    )

    result = client.simulate(seed)

    assert result.verdict == "HIGH"
    assert result.simulation_id == "s1"
    assert result.report_id == "r1"
    assert "backlash" in result.report_markdown
    assert backend.run_status_calls >= 2  # polling actually looped
    assert "multipart/form-data" in backend.ontology_content_type


class FakeLLM:
    def __init__(self, response):
        self.response = response

    def complete(self, prompt):
        return self.response


def test_llm_classifies_report(monkeypatch):
    backend = FakeBackend()
    monkeypatch.setattr("atlas.prediction.mirofish.urlopen", backend)

    # Report text is full of backlash terms (heuristic would say HIGH), but the
    # LLM overrides to LOW -> proves the LLM path drives the verdict.
    llm = FakeLLM('{"verdict":"LOW","risk_score":0.15}')
    client = MiroFishClient(
        "http://localhost:5001", max_rounds=3, poll_interval=0, deadline=30, llm=llm
    )
    seed = PredictionSeed(requirement="q", documents=[])

    result = client.simulate(seed)
    assert result.verdict == "LOW"
    assert result.risk_score == 0.15


def test_backend_unreachable_message(monkeypatch):
    from urllib.error import URLError

    def boom(req, timeout=None):
        raise URLError("Connection refused")

    monkeypatch.setattr("atlas.prediction.mirofish.urlopen", boom)
    client = MiroFishClient("http://localhost:5001", poll_interval=0)
    seed = PredictionSeed(requirement="x", documents=[])

    try:
        client.simulate(seed)
    except RuntimeError as exc:
        assert "backend running" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")
