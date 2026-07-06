import os
from pathlib import Path

import pytest

from atlas.storage.sqlite import default_db_path


def test_default_db_path_windows(monkeypatch, tmp_path):
    if os.name != "nt":
        pytest.skip("Windows-only path test.")
    base = tmp_path / "LocalAppData"
    monkeypatch.setenv("LOCALAPPDATA", str(base))
    path = default_db_path()
    assert path == (base / "atlas" / "atlas.db").resolve()


def test_default_db_path_posix():
    if os.name == "nt":
        pytest.skip("POSIX-only path test.")
    path = default_db_path()
    assert path == (Path.home() / ".atlas" / "atlas.db").resolve()
