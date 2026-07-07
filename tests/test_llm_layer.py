import json

from atlas.llm.anthropic import AnthropicClient
from atlas.llm.base import LLMClient, build_llm_from_env


class EchoClient(LLMClient):
    """Minimal client implementing only complete()."""

    def __init__(self, response):
        self._response = response

    def complete(self, prompt: str) -> str:
        return self._response


# -- Fake Anthropic SDK objects ------------------------------------------------


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Usage:
    def __init__(self, i, o):
        self.input_tokens = i
        self.output_tokens = o


class _Response:
    def __init__(self, text, i=10, o=20):
        self.content = [_Block(text)]
        self.usage = _Usage(i, o)


class _Messages:
    def __init__(self, text):
        self._text = text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response(self._text)


class _FakeSDK:
    def __init__(self, text):
        self.messages = _Messages(text)


def test_base_complete_structured_parses_json():
    result = EchoClient('{"verdict":"HIGH","risk_score":0.8}').complete_structured(
        "x", {"type": "object"}
    )
    assert result["verdict"] == "HIGH"


def test_anthropic_complete_and_usage():
    sdk = _FakeSDK("hello world")
    client = AnthropicClient("key", "claude-opus-4-8", client=sdk)
    assert client.complete("hi") == "hello world"
    assert client.last_usage.input_tokens == 10
    assert client.last_usage.output_tokens == 20
    # opus pricing: 10*5/1e6 + 20*25/1e6
    assert client.last_usage.cost_usd > 0


def test_anthropic_structured_uses_output_config():
    sdk = _FakeSDK('{"verdict":"LOW","risk_score":0.1}')
    client = AnthropicClient("key", "claude-opus-4-8", client=sdk)
    parsed = client.complete_structured("p", {"type": "object"})
    assert parsed["verdict"] == "LOW"
    # the schema was passed via output_config.format
    assert "output_config" in sdk.messages.calls[0]


def test_from_env_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    try:
        AnthropicClient.from_env()
    except RuntimeError as exc:
        assert "ANTHROPIC_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_build_llm_from_env_no_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ATLAS_LLM_PROVIDER", "openai")
    assert build_llm_from_env() is None


def test_build_llm_from_env_selects_anthropic(monkeypatch):
    monkeypatch.setenv("ATLAS_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    client = build_llm_from_env()
    assert isinstance(client, AnthropicClient)
