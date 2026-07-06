from pathlib import Path

from atlas.board_meeting.manifest import build_manifest


def test_manifest_builder_shape(tmp_path):
    manifest = build_manifest(
        day="2026-01-11",
        output_dir=Path("/tmp/audio"),
        audio_format="mp3",
        enable_llm=True,
        entries=[{"head": "operations", "chunk_index": 1, "path": "x.mp3"}],
    )
    assert manifest["schema"].endswith("v1")
    assert manifest["date"] == "2026-01-11"
    assert manifest["audio_format"] == "mp3"
    assert manifest["files"][0]["head"] == "operations"
