import io
import json
from pathlib import Path
import sys
import pytest


pytestmark = pytest.mark.unit


def _ensure_import():
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _call(app, method: str, path: str, query: str = ""):
    raw = b""
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "SERVER_NAME": "unit",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(raw),
        "CONTENT_LENGTH": "0",
    }
    status_headers = []

    def start_response(status, headers):
        status_headers.append((status, headers))

    data = b"".join(app.wsgi_app(env, start_response))
    status, headers = status_headers[0]
    return status, dict(headers), data


def test_naics_roots_and_children(tmp_path: Path):
    _ensure_import()
    from neo_agent.intake_app import create_app

    app = create_app(base_dir=tmp_path)
    st, hdr, raw = _call(app, "GET", "/api/naics/roots")
    assert st == "200 OK"
    roots = json.loads(raw.decode("utf-8")).get("items")
    assert isinstance(roots, list)
    # Fetch children of first root if present
    parent = roots[0]["code"] if roots else "54"
    st, hdr, raw = _call(app, "GET", f"/api/naics/children/{parent}", query="level=1")
    assert st == "200 OK"
    items = json.loads(raw.decode("utf-8")).get("items")
    assert isinstance(items, list)
