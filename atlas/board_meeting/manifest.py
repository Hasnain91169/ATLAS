from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_manifest(
    *,
    day: str,
    output_dir: Path,
    audio_format: str,
    enable_llm: bool,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": "atlas.board_meeting.manifest.v1",
        "date": day,
        "output_dir": str(output_dir),
        "audio_format": audio_format,
        "enable_llm": enable_llm,
        "openai_model": os.environ.get("OPENAI_MODEL"),
        "elevenlabs_model": os.environ.get("ELEVENLABS_MODEL"),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "files": entries,
    }


def write_manifest(output_dir: Path, day: str, manifest: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{day}-manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return path
