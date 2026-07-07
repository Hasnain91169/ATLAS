from __future__ import annotations

import json
import os
import time
from typing import Any

from atlas.llm.base import LLMClient, LLMUsage

DEFAULT_MODEL = "claude-opus-4-8"

# USD per input / output token, by model prefix (per 1M -> per token).
_PRICING = {
    "claude-opus-4": (5.00 / 1_000_000, 25.00 / 1_000_000),
    "claude-sonnet-5": (3.00 / 1_000_000, 15.00 / 1_000_000),
    "claude-haiku-4-5": (1.00 / 1_000_000, 5.00 / 1_000_000),
}


class AnthropicClient(LLMClient):
    """Claude client via the official ``anthropic`` SDK (imported lazily).

    Kept out of the core dependency set: install with ``pip install anthropic``
    (or ``pip install -e ".[anthropic]"``). Selected via
    ``ATLAS_LLM_PROVIDER=anthropic``.
    """

    def __init__(self, api_key: str, model: str, *, client: Any = None, max_tokens: int = 1024):
        self._api_key = api_key
        self._model = model
        self._client = client
        self._max_tokens = max_tokens
        self.last_usage: LLMUsage | None = None

    @classmethod
    def from_env(cls) -> "AnthropicClient":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY must be set to use the Anthropic provider.")
        model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)
        return cls(api_key, model)

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - depends on env
                raise RuntimeError(
                    "The 'anthropic' package is required for the Anthropic provider. "
                    "Install it with: pip install anthropic"
                ) from exc
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def complete(self, prompt: str) -> str:
        response = self._create(prompt)
        return _text(response).strip()

    def complete_structured(self, prompt: str, schema: dict) -> dict:
        response = self._create(
            prompt,
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        return json.loads(_text(response))

    def _create(self, prompt: str, **extra: Any) -> Any:
        client = self._ensure_client()
        start = time.perf_counter()
        response = client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
            **extra,
        )
        self.last_usage = _usage(response, self._model, time.perf_counter() - start)
        return response


def _text(response: Any) -> str:
    parts = [
        block.text
        for block in getattr(response, "content", [])
        if getattr(block, "type", None) == "text"
    ]
    if not parts:
        raise RuntimeError("Anthropic response contained no text block.")
    return "".join(parts)


def _usage(response: Any, model: str, elapsed_s: float) -> LLMUsage:
    usage = getattr(response, "usage", None)
    in_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    out_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    in_rate, out_rate = next(
        (rates for prefix, rates in _PRICING.items() if model.startswith(prefix)),
        (0.0, 0.0),
    )
    return LLMUsage(
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        latency_ms=elapsed_s * 1000.0,
        cost_usd=in_tokens * in_rate + out_tokens * out_rate,
    )
