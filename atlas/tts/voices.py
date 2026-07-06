from __future__ import annotations

import os


_VOICE_ENV = {
    "atlas": "ELEVENLABS_VOICE_ATLAS",
    "operations": "ELEVENLABS_VOICE_OPERATIONS",
    "risk": "ELEVENLABS_VOICE_RISK",
    "risk & compliance": "ELEVENLABS_VOICE_RISK",
    "risk and compliance": "ELEVENLABS_VOICE_RISK",
    "finance": "ELEVENLABS_VOICE_FINANCE",
    "learning": "ELEVENLABS_VOICE_LEARNING",
}


def get_voice_id(name: str) -> str:
    key = name.strip().lower()
    env_var = _VOICE_ENV.get(key)
    if not env_var:
        raise RuntimeError(f"No voice mapping for {name}.")
    value = os.environ.get(env_var)
    if not value:
        raise RuntimeError(f"{env_var} must be set.")
    return value
