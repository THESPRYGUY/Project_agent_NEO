from __future__ import annotations

import io
import json
from pathlib import Path

import sys
from pathlib import Path as _Path

ROOT = _Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neo_agent.intake_app import create_app


def _call(app, method: str, path: str, body: dict | None = None):
    raw = json.dumps(body or {}).encode("utf-8")
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "testserver",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(raw),
        "CONTENT_LENGTH": str(len(raw)),
    }
    status_headers = []
    def start_response(status, headers):
        status_headers.append((status, headers))
    resp = b"".join(app.wsgi_app(env, start_response))
    status = status_headers[0][0]
    return status, dict(status_headers[0][1]), resp


def test_identity_generate_endpoint(tmp_path: Path):
    app = create_app(base_dir=tmp_path)
    payload = {
        "naics_code": "541512",
        "business_func": "it_ops",
        "role_code": "AIA-P",
        "agent_name": "Smoke Test Agent",
    }
    status, _, body = _call(app, "POST", "/api/identity/generate", payload)
    assert status == "200 OK", body
    data = json.loads(body.decode("utf-8"))
    assert isinstance(data.get("agent_id"), str) and data["agent_id"], data

    # Determinism: same input -> same id
    status2, _, body2 = _call(app, "POST", "/api/identity/generate", payload)
    assert status2 == "200 OK"
    assert json.loads(body2.decode("utf-8"))["agent_id"] == data["agent_id"]
