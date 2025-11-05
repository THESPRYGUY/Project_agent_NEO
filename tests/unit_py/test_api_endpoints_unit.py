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


def _call(app, method: str, path: str, query: str = "", body: bytes = b""):
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


def test_naics_search_and_detail(tmp_path: Path):
    _ensure_import()
    from neo_agent.intake_app import create_app

    app = create_app(base_dir=tmp_path)
    st, _, raw = _call(app, "GET", "/api/naics/search", query="q=law")
    assert st == "200 OK"
    items = json.loads(raw.decode("utf-8")).get("items")
    assert isinstance(items, list)
    code = items[0]["code"] if items else "541110"
    st, _, raw = _call(app, "GET", f"/api/naics/code/{code}")
    assert st == "200 OK"
    entry = json.loads(raw.decode("utf-8")).get("entry")
    assert isinstance(entry, dict)


def test_identity_generate_and_persona_config_state(tmp_path: Path):
    _ensure_import()
    from neo_agent.intake_app import create_app

    app = create_app(base_dir=tmp_path)
    # identity generate
    payload = json.dumps(
        {
            "naics_code": "541110",
            "business_function": "legal",
            "role_code": "AIA-P",
            "agent_name": "Neo",
        }
    ).encode("utf-8")
    st, _, raw = _call(app, "POST", "/api/identity/generate", body=payload)
    assert st == "200 OK"
    agent_id = json.loads(raw.decode("utf-8")).get("agent_id")
    assert isinstance(agent_id, str) and agent_id
    # persona config
    st, _, raw = _call(app, "GET", "/api/persona/config")
    assert st == "200 OK"
    cfg = json.loads(raw.decode("utf-8"))
    assert isinstance(cfg, dict)
    # persona state roundtrip
    st, _, raw = _call(
        app,
        "POST",
        "/api/persona/state",
        body=json.dumps({"tone": "crisp"}).encode("utf-8"),
    )
    assert st == "200 OK"
    st, _, raw = _call(app, "GET", "/api/persona/state")
    assert st == "200 OK"
    state = json.loads(raw.decode("utf-8"))
    assert isinstance(state, dict)
