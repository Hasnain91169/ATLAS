from atlas.tts.elevenlabs import ElevenLabsClient


def test_elevenlabs_accept_header_for_wav(tmp_path, monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=20):
        captured["accept"] = req.headers.get("Accept")
        class FakeResponse:
            def read(self):
                return b"wav-data"
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
        return FakeResponse()

    monkeypatch.setattr("atlas.tts.elevenlabs.urlopen", fake_urlopen)
    client = ElevenLabsClient("key", "https://api.example.com", "model")
    out_path = tmp_path / "voice.wav"

    result = client.synthesize("hello", "voice-id", out_path, audio_format="wav")

    assert captured["accept"] == "audio/wav"
    assert result.suffix == ".wav"
