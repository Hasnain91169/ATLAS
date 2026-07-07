from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMUsage:
    """Token/cost/latency for a single completion, for tracing and cost awareness."""

    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0


class LLMClient(ABC):
    #: Populated by clients after each call; None until the first completion.
    last_usage: LLMUsage | None = None

    @abstractmethod
    def complete(self, prompt: str) -> str:
        raise NotImplementedError

    def complete_structured(self, prompt: str, schema: dict) -> dict:
        """Return a JSON object matching ``schema``.

        Default implementation parses ``complete()`` output as JSON; providers
        with native structured-output support (e.g. Anthropic) override this to
        constrain generation to the schema.
        """
        return json.loads(self.complete(prompt))


def build_llm_from_env() -> LLMClient | None:
    """Select an LLM client from ``ATLAS_LLM_PROVIDER`` (openai | anthropic).

    Returns None when the selected provider has no key configured, so callers
    can fall back to deterministic behavior.
    """
    provider = os.environ.get("ATLAS_LLM_PROVIDER", "openai").lower()
    try:
        if provider == "anthropic":
            from atlas.llm.anthropic import AnthropicClient

            return AnthropicClient.from_env()
        from atlas.llm.openai import OpenAIClient

        return OpenAIClient.from_env()
    except RuntimeError:
        return None
