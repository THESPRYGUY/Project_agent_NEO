import io
import json
import os
import sys
from pathlib import Path
import pytest


pytestmark = pytest.mark.unit


def _call_raw(app, method: str, path: str, raw: bytes):
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


def test_save_missing_body_400(tmp_path: Path):
    _ensure_import()
    from neo_agent.intake_app import create_app

    app = create_app(base_dir=tmp_path)
    # Empty body -> treated as {} and triggers schema errors
    st, hdrs, raw = _call_raw(app, "POST", "/save", b"")
    assert st.startswith("400")
    body = json.loads(raw.decode("utf-8"))
    assert body.get("status") == "invalid"


def test_save_invalid_json_400(tmp_path: Path):
    _ensure_import()
    from neo_agent.intake_app import create_app

    app = create_app(base_dir=tmp_path)
    st, _, raw = _call_raw(app, "POST", "/save", b"{not-json}")
    assert st.startswith("400")
    body = json.loads(raw.decode("utf-8"))
    assert body.get("status") == "invalid"
    assert any("Invalid JSON" in e for e in body.get("errors", []))


def test_save_schema_conflict_400(tmp_path: Path):
    _ensure_import()
    from neo_agent.intake_app import create_app

    app = create_app(base_dir=tmp_path)
    payload = {
        "intake_version": "v3.0",
        "legacy": {},
        "identity": {"agent_id": "X", "display_name": "X", "owners": ["CAIO"]},
        "context": {"naics": {"code": "541110"}},
        "role": {"function_code": "fn", "role_code": "rc"},
        "governance_eval": {
            "gates": {"PRI_min": 0.95, "hallucination_max": 0.02, "audit_min": 0.9}
        },
    }
    st, _, raw = _call_raw(app, "POST", "/save", json.dumps(payload).encode("utf-8"))
    assert st.startswith("400")
    body = json.loads(raw.decode("utf-8"))
    assert body.get("status") == "invalid"
    assert any("Legacy field not allowed in v3" in e for e in body.get("errors", []))
