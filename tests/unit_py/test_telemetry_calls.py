import io
import json
import os
import sys
from pathlib import Path
import pytest


pytestmark = pytest.mark.unit


def _ensure_import():
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _wsgi_call(app, method: str, path: str, query: str = "", body: bytes = b""):
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "SERVER_NAME": "unit",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(body),
        "CONTENT_LENGTH": str(len(body)),
    }
    status_headers = []
    def start_response(status, headers):
        status_headers.append((status, headers))
    data = b"".join(app.wsgi_app(env, start_response))
    status, headers = status_headers[0]
    return status, dict(headers), data


def test_last_build_emits_event(tmp_path: Path, monkeypatch):
    _ensure_import()
    import neo_agent.intake_app as appmod
    from neo_agent.intake_app import create_app

    called = {}
    def _emit(evt, payload):
        called[evt] = payload
    monkeypatch.setattr(appmod, "emit_event", _emit)

    out_root = tmp_path / "root"
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "_last_build.json").write_text(json.dumps({
        "timestamp": "2025-01-01T00:00:00Z", "outdir": str(out_root / 'AGT' / 'TS'),
        "file_count": 20, "parity": {}, "integrity_errors": []
    }), encoding="utf-8")
    os.environ["NEO_REPO_OUTDIR"] = str(out_root)
    app = create_app(base_dir=tmp_path)
    st, _, _ = _wsgi_call(app, "GET", "/last-build")
    assert st == "200 OK"
    assert "last_build_read" in called


def test_zip_download_emits_event(tmp_path: Path, monkeypatch):
    _ensure_import()
    import neo_agent.intake_app as appmod
    from neo_agent.intake_app import create_app

    called = {}
    def _emit(evt, payload):
        called[evt] = payload
    monkeypatch.setattr(appmod, "emit_event", _emit)

    os.environ["NEO_REPO_OUTDIR"] = str(tmp_path / "root")
    app = create_app(base_dir=tmp_path)
    # Create small outdir
    outdir = Path(os.environ["NEO_REPO_OUTDIR"]) / "AGT" / "TS"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "a.txt").write_text("x", encoding="utf-8")
    st, _, data = _wsgi_call(app, "GET", "/build/zip", query=f"outdir={outdir}")
    assert st == "200 OK"
    assert "zip_download" in called

