import threading

from atlas.cli import run_doctor
from atlas.mobile.server import create_server


def test_doctor_reachable_server_without_token_hint(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ATLAS_MOBILE_TOKEN", raising=False)
    db_path = tmp_path / "atlas.db"
    server = create_server("127.0.0.1", 0, db_path, "secret-token")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    server_url = f"http://{host}:{port}"

    try:
        run_doctor(str(db_path), server_url)
        output = capsys.readouterr().out
        assert "ATLAS_MOBILE_TOKEN is missing" not in output
        assert "Server reachable; token required for /api/v1/* endpoints." in output
    finally:
        server.shutdown()


def test_doctor_reports_mirofish_backend_unreachable(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MIROFISH_BASE_URL", "http://127.0.0.1:1")
    db_path = tmp_path / "atlas.db"

    run_doctor(str(db_path), "http://127.0.0.1:0")
    output = capsys.readouterr().out
    assert "MiroFish Backend: NO" in output
    assert "MiroFish backend not reachable" in output
