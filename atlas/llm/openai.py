from __future__ import annotations

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from atlas.llm.base import LLMClient, LLMUsage

DEFAULT_BASE_URL = "https://api.openai.com"
USER_AGENT = "atlas/0.1"


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str, base_url: str):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self.last_usage: LLMUsage | None = None

    @classmethod
    def from_env(cls) -> "OpenAIClient":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY must be set to enable LLM calls.")
        model = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
        base_url = os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL)
        return cls(api_key, model, base_url)

    def complete(self, prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "You are a concise executive assistant."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 512,
        }
        data = json.dumps(payload).encode("utf-8")
        url = f"{self._base_url}/v1/chat/completions"
        req = Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        start = time.perf_counter()
        try:
            with urlopen(req, timeout=15) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            message = _extract_error_message(exc)
            raise RuntimeError(f"OpenAI HTTP {exc.code}: {message}") from None
        except URLError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc.reason}") from None
        choices = response_payload.get("choices", [])
        if not choices:
            raise RuntimeError("OpenAI response missing choices.")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not content:
            raise RuntimeError("OpenAI response missing content.")
        usage = response_payload.get("usage") or {}
        self.last_usage = LLMUsage(
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
            latency_ms=(time.perf_counter() - start) * 1000.0,
        )
        return str(content).strip()


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
        message = (
            payload.get("error", {}).get("message")
            if isinstance(payload, dict)
            else None
        )
        if message:
            return str(message)
        return body.strip()[:200]
    return str(exc.reason)
