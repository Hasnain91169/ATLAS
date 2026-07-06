from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class ElevenLabsClient:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    @classmethod
    def from_env(cls) -> "ElevenLabsClient":
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise RuntimeError("ELEVENLABS_API_KEY must be set.")
        base_url = os.environ.get("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io")
        model = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
        return cls(api_key, base_url, model)

    def synthesize(
        self, text: str, voice_id: str, out_path: Path, audio_format: str = "mp3"
    ) -> Path:
        url = f"{self._base_url}/v1/text-to-speech/{voice_id}"
        accept = "audio/mpeg" if audio_format == "mp3" else "audio/wav"
        payload = {
            "text": text,
            "model_id": self._model,
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.7},
        }
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=data,
            headers={
                "xi-api-key": self._api_key,
                "Content-Type": "application/json",
                "Accept": accept,
                "User-Agent": "ATLAS/tts",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=20) as response:
                audio = response.read()
        except HTTPError as exc:
            snippet = ""
            try:
                snippet = exc.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                snippet = ""
            message = f"ElevenLabs HTTP {exc.code}"
            if snippet:
                message = f"{message}: {snippet}"
            raise RuntimeError(message) from None

        if not audio:
            raise RuntimeError("ElevenLabs returned empty audio response.")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(audio)
        return out_path
