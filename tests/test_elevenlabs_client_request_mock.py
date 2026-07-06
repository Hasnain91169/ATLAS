import io
from pathlib import Path
from urllib.error import HTTPError

from atlas.tts.elevenlabs import ElevenLabsClient


class FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_elevenlabs_client_writes_audio(tmp_path, monkeypatch):
    def fake_urlopen(req, timeout=20):
        return FakeResponse(b"mp3-bytes")

    monkeypatch.setattr("atlas.tts.elevenlabs.urlopen", fake_urlopen)
    client = ElevenLabsClient("key", "https://api.example.com", "model")
    out_path = tmp_path / "voice.mp3"

    result = client.synthesize("hello", "voice-id", out_path, audio_format="mp3")

    assert result.exists()
    assert result.read_bytes() == b"mp3-bytes"


def test_elevenlabs_client_http_error(tmp_path, monkeypatch):
    def fake_urlopen(req, timeout=20):
        body = io.BytesIO(b"Bad request")
        raise HTTPError(req.full_url, 400, "Bad Request", {}, body)

    monkeypatch.setattr("atlas.tts.elevenlabs.urlopen", fake_urlopen)
    client = ElevenLabsClient("key", "https://api.example.com", "model")
    out_path = tmp_path / "voice.mp3"

    try:
        client.synthesize("hello", "voice-id", out_path, audio_format="mp3")
    except RuntimeError as exc:
        assert "ElevenLabs HTTP 400" in str(exc)
        assert "Bad request" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")
