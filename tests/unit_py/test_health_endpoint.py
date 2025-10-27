import io
import json
import os
import sys
from pathlib import Path
import pytest


pytestmark = pytest.mark.unit


def _call(app, method: str, path: str):
    body = b""
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "unit",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(body),
        "CONTENT_LENGTH": "0",
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


def test_health_ok_headers(tmp_path: Path):
    _ensure_import()
    from neo_agent.intake_app import create_app
    app = create_app(base_dir=tmp_path)
    st, hdrs, raw = _call(app, "GET", "/health")
    assert st == "200 OK"
    h = {k.lower(): v for k, v in hdrs.items()}
    assert h.get("cache-control", "").startswith("no-store")
    assert h.get("x-neo-intake-version") == "v3.0"
    payload = json.loads(raw.decode("utf-8"))
    assert payload.get("status") == "ok"

