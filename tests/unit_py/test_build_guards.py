import io
import json
import os
import sys
from pathlib import Path
import pytest


pytestmark = pytest.mark.unit


def _call(app, method: str, path: str):
    raw = b"{}" if method == "POST" else b""
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "unit",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(raw),
        "CONTENT_LENGTH": str(len(raw)),
    }
    status_headers = []
    def start_response(status, headers):
        status_headers.append((status, headers))
    data = b"".join(app.wsgi_app(env, start_response))
    status, headers = status_headers[0]
    return status, dict(headers), data


def _ensure_import():
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def test_build_missing_inputs_400(tmp_path: Path):
    _ensure_import()
    os.environ["NEO_REPO_OUTDIR"] = str((tmp_path / "out").resolve())
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    st, headers, raw = _call(app, "POST", "/build")
    assert st == "400 Bad Request"
    payload = json.loads(raw.decode("utf-8"))
    assert payload.get("status") == "error"
    assert "agent_profile.json not found" in " ".join(payload.get("issues", []))

