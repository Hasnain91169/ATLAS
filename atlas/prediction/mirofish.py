from __future__ import annotations

import json
import os
import sys
import time
import uuid
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from atlas.llm.base import LLMClient
from atlas.prediction.assess import assess_reaction
from atlas.prediction.base import PredictionClient
from atlas.prediction.models import PredictionResult, PredictionSeed

# Self-hosted MiroFish backend (github.com/666ghj/MiroFish). Local Flask app,
# no auth, CORS open. Not a hosted SaaS endpoint. Every response is wrapped as
# {"success": bool, "data": {...}}; _send() unwraps `data` for the callers.
DEFAULT_BASE_URL = "http://localhost:5001"
USER_AGENT = "atlas/0.1"

# Terminal status strings the backend uses across its async stages. Graph/report
# tasks report "completed"; simulation prepare reports "ready"; a finished run
# reports runner_status "completed".
_DONE = {"completed", "done", "finished", "ready", "success", "succeeded"}
_FAILED = {"failed", "error", "stopped", "cancelled", "canceled"}


class MiroFishClient(PredictionClient):
    """Drives MiroFish's 6-stage async simulation pipeline to one prediction.

    Stages: ontology/generate -> graph/build -> simulation/create ->
    simulation/prepare -> simulation/start -> report/generate. Each long
    stage is polled until terminal. Field names track the backend's
    /api/{graph,simulation,report} blueprints and are parsed defensively.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        platform: str = "reddit",
        max_rounds: int = 10,
        poll_interval: float = 5.0,
        deadline: float = 1800.0,
        request_timeout: float = 60.0,
        llm: LLMClient | None = None,
        verbose: bool = False,
    ):
        self._base_url = base_url.rstrip("/")
        self._platform = platform
        self._max_rounds = max_rounds
        self._poll_interval = poll_interval
        self._deadline = deadline
        self._request_timeout = request_timeout
        self._llm = llm
        self._verbose = verbose

    @classmethod
    def from_env(cls, verbose: bool = False) -> "MiroFishClient":
        base_url = os.environ.get("MIROFISH_BASE_URL", DEFAULT_BASE_URL)
        platform = os.environ.get("MIROFISH_PLATFORM", "reddit")
        max_rounds = int(os.environ.get("MIROFISH_MAX_ROUNDS", "10"))
        return cls(
            base_url,
            platform=platform,
            max_rounds=max_rounds,
            llm=_llm_from_env(),
            verbose=verbose or os.environ.get("MIROFISH_VERBOSE") == "1",
        )

    # -- pipeline ---------------------------------------------------------

    def simulate(self, seed: PredictionSeed) -> PredictionResult:
        deadline = time.monotonic() + self._deadline

        project_id = self._generate_ontology(seed)
        graph_id = self._build_graph(project_id, deadline)
        simulation_id = self._create_simulation(project_id, graph_id)
        self._prepare(simulation_id, deadline)
        self._run(simulation_id, deadline)
        report = self._generate_report(simulation_id, deadline)

        markdown = str(report.get("markdown_content", ""))
        if not markdown:
            raise RuntimeError("MiroFish report missing markdown_content.")
        verdict, risk_score = assess_reaction(markdown, seed.requirement, self._llm)
        return PredictionResult(
            report_markdown=markdown,
            outline=str(report.get("outline", "") or ""),
            verdict=verdict,
            risk_score=risk_score,
            simulation_id=str(simulation_id),
            report_id=str(report.get("report_id", "") or "") or None,
            raw=report,
        )

    def _generate_ontology(self, seed: PredictionSeed) -> str:
        fields = {"simulation_requirement": seed.requirement}
        if seed.project_name:
            fields["project_name"] = seed.project_name
        if seed.additional_context:
            fields["additional_context"] = seed.additional_context
        files = [(doc.filename, doc.content) for doc in seed.documents] or [
            ("seed.md", seed.requirement)
        ]
        payload = self._post_multipart("/api/graph/ontology/generate", fields, files)
        project_id = payload.get("project_id")
        if not project_id:
            raise RuntimeError("MiroFish ontology response missing project_id.")
        return str(project_id)

    def _build_graph(self, project_id: str, deadline: float) -> str:
        started = self._post_json("/api/graph/build", {"project_id": project_id})
        task_id = started.get("task_id")
        if not task_id:
            raise RuntimeError("MiroFish graph build response missing task_id.")
        status = self._poll(
            lambda: self._get_json(f"/api/graph/task/{task_id}"), deadline, "graph build"
        )
        graph_id = status.get("graph_id") or _nested(status, "result", "graph_id")
        if not graph_id:
            raise RuntimeError("MiroFish graph build finished without a graph_id.")
        return str(graph_id)

    def _create_simulation(self, project_id: str, graph_id: str) -> str:
        payload = self._post_json(
            "/api/simulation/create",
            {
                "project_id": project_id,
                "graph_id": graph_id,
                "enable_reddit": self._platform in {"reddit", "parallel"},
                "enable_twitter": self._platform in {"twitter", "parallel"},
            },
        )
        simulation_id = payload.get("simulation_id")
        if not simulation_id:
            raise RuntimeError("MiroFish create response missing simulation_id.")
        return str(simulation_id)

    def _prepare(self, simulation_id: str, deadline: float) -> None:
        started = self._post_json(
            "/api/simulation/prepare",
            {"simulation_id": simulation_id, "use_llm_for_profiles": True},
        )
        task_id = started.get("task_id")
        self._poll(
            lambda: self._post_json(
                "/api/simulation/prepare/status",
                {"task_id": task_id, "simulation_id": simulation_id},
            ),
            deadline,
            "prepare",
        )

    def _run(self, simulation_id: str, deadline: float) -> None:
        self._post_json(
            "/api/simulation/start",
            {
                "simulation_id": simulation_id,
                "platform": self._platform,
                "max_rounds": self._max_rounds,
            },
        )
        self._poll(
            lambda: self._get_json(f"/api/simulation/{simulation_id}/run-status"),
            deadline,
            "simulation run",
            done=_run_done,
        )

    def _generate_report(self, simulation_id: str, deadline: float) -> dict[str, Any]:
        started = self._post_json(
            "/api/report/generate", {"simulation_id": simulation_id}
        )
        report_id = started.get("report_id")
        task_id = started.get("task_id")
        self._poll(
            lambda: self._post_json(
                "/api/report/generate/status",
                {"task_id": task_id, "simulation_id": simulation_id},
            ),
            deadline,
            "report",
        )
        if report_id:
            return self._get_json(f"/api/report/{report_id}")
        return self._get_json(f"/api/report/by-simulation/{simulation_id}")

    # -- polling ----------------------------------------------------------

    def _poll(
        self,
        fetch: Callable[[], dict[str, Any]],
        deadline: float,
        stage: str,
        done: Callable[[dict[str, Any]], bool] = None,  # type: ignore[assignment]
    ) -> dict[str, Any]:
        done = done or _status_done
        while True:
            payload = fetch()
            if _status_failed(payload):
                message = payload.get("message") or payload.get("error") or "unknown"
                raise RuntimeError(f"MiroFish {stage} failed: {message}")
            if done(payload):
                return payload
            if time.monotonic() >= deadline:
                raise RuntimeError(f"MiroFish {stage} timed out.")
            time.sleep(self._poll_interval)

    # -- transport --------------------------------------------------------

    def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8")
        req = Request(
            f"{self._base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
            method="POST",
        )
        return self._send(req, path)

    def _get_json(self, path: str) -> dict[str, Any]:
        req = Request(
            f"{self._base_url}{path}",
            headers={"User-Agent": USER_AGENT},
            method="GET",
        )
        return self._send(req, path)

    def _post_multipart(
        self, path: str, fields: dict[str, str], files: list[tuple[str, str]]
    ) -> dict[str, Any]:
        boundary = f"----atlas{uuid.uuid4().hex}"
        body = _encode_multipart(boundary, fields, files)
        req = Request(
            f"{self._base_url}{path}",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        return self._send(req, path)

    def _send(self, req: Request, path: str) -> dict[str, Any]:
        try:
            with urlopen(req, timeout=self._request_timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(
                f"MiroFish HTTP {exc.code} on {path}: {_extract_error_message(exc)}"
            ) from None
        except URLError as exc:
            raise RuntimeError(
                f"MiroFish request to {path} failed: {exc.reason}. "
                "Is the backend running at "
                f"{self._base_url}?"
            ) from None
        data = _unwrap(payload, path)
        if self._verbose:
            print(f"[mirofish] {req.method} {path} -> {json.dumps(data)[:600]}", file=sys.stderr)
        return data


def _unwrap(payload: Any, path: str) -> dict[str, Any]:
    """Peel MiroFish's {"success": bool, "data": {...}} envelope for callers."""
    if isinstance(payload, dict) and "success" in payload:
        if not payload.get("success", False):
            raise RuntimeError(f"MiroFish {path}: {_err_text(payload.get('error'))}")
        data = payload.get("data")
        if isinstance(data, dict):
            return data
        return {"data": data} if data is not None else {}
    return payload if isinstance(payload, dict) else {}


def _err_text(error: Any) -> str:
    if isinstance(error, dict):
        return str(error.get("message") or error)
    return str(error) if error else "request failed"


# -- helpers --------------------------------------------------------------


def _llm_from_env() -> LLMClient | None:
    """Build an LLM client for report classification, or None to use the heuristic."""
    from atlas.llm.openai import OpenAIClient

    try:
        return OpenAIClient.from_env()
    except RuntimeError:
        return None


def _status_done(payload: dict[str, Any]) -> bool:
    status = str(payload.get("status", "")).lower()
    if status in _DONE:
        return True
    progress = payload.get("progress")
    return isinstance(progress, (int, float)) and progress >= 100


def _status_failed(payload: dict[str, Any]) -> bool:
    # Most stages report `status`; the run stage reports `runner_status`.
    for key in ("status", "runner_status"):
        if str(payload.get(key, "")).lower() in _FAILED:
            return True
    return False


def _run_done(payload: dict[str, Any]) -> bool:
    # run-status uses runner_status + current_round/total_rounds (no `status`).
    if str(payload.get("runner_status", "")).lower() == "completed":
        return True
    current = payload.get("current_round")
    total = payload.get("total_rounds")
    return bool(total) and isinstance(current, (int, float)) and current >= total


def _nested(payload: dict[str, Any], *keys: str) -> Any:
    node: Any = payload
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _encode_multipart(
    boundary: str, fields: dict[str, str], files: list[tuple[str, str]]
) -> bytes:
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        )
        parts.append(f"{value}\r\n".encode())
    for filename, content in files:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'.encode()
        )
        parts.append(b"Content-Type: text/plain\r\n\r\n")
        parts.append(content.encode("utf-8"))
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts)


def _extract_error_message(exc: HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8")
    except Exception:
        body = ""
    if body:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {}
        # MiroFish errors are {"success": false, "error": "..."}; other APIs
        # nest {"error": {"message": "..."}}. Handle both.
        message = _err_text(payload.get("error")) if isinstance(payload, dict) else None
        if message and message != "request failed":
            return str(message)
        return body.strip()[:200]
    return str(exc.reason)
