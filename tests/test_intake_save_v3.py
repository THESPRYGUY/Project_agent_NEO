from __future__ import annotations

import io
import json
from pathlib import Path

from neo_agent.intake_app import create_app


def _call(app, method: str, path: str, payload: dict | None = None):
    body = json.dumps(payload or {}).encode("utf-8")
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "testserver",
        "SERVER_PORT": "80",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(body),
        "CONTENT_LENGTH": str(len(body)),
    }
    status_headers: list[tuple[str, list[tuple[str, str]]]] = []

    def start_response(status: str, headers: list[tuple[str, str]]):
        status_headers.append((status, headers))

    resp_iter = app.wsgi_app(environ, start_response)
    raw = b"".join(resp_iter)
    status = status_headers[0][0]
    headers = {k.lower(): v for k, v in status_headers[0][1]}
    return status, headers, raw


def _valid_payload():
    return {
        "intake_version": "v3.0",
        "identity": {
            "agent_id": "AGENT-123",
            "display_name": "Agent 123",
            "owners": ["CAIO", "CPA"],
        },
        "context": {"naics": {"code": "541110"}, "region": ["CA"]},
        "role": {
            "function_code": "legal_compliance",
            "role_code": "AIA-P",
            "role_title": "Lead",
        },
        "governance_eval": {
            "gates": {"PRI_min": 0.95, "hallucination_max": 0.02, "audit_min": 0.9}
        },
    }


def test_save_v3_persists_and_normalizes(tmp_path: Path):
    app = create_app(base_dir=tmp_path)
    status, headers, raw = _call(app, "POST", "/save", _valid_payload())
    assert status == "200 OK"
    assert headers.get("cache-control", "").startswith("no-store")
    assert headers.get("x-neo-intake-version") == "v3.0"
    payload = json.loads(raw.decode("utf-8"))
    assert payload.get("status") == "ok"

    # persisted file
    profile_path = tmp_path / "agent_profile.json"
    assert profile_path.exists()
    saved = json.loads(profile_path.read_text(encoding="utf-8"))
    # normalizer injects role_profile/sector_profile
    assert (saved.get("role_profile") or {}).get("archetype") == "AIA-P"
    assert (saved.get("sector_profile") or {}).get("region") == ["CA"]


def test_save_v3_rejects_missing_fields(tmp_path: Path):
    app = create_app(base_dir=tmp_path)
    payload = _valid_payload()
    del payload["identity"]["display_name"]
    status, _, raw = _call(app, "POST", "/save", payload)
    assert status.startswith("400")
    body = json.loads(raw.decode("utf-8"))
    assert body.get("status") == "invalid"
    assert any("identity.display_name" in e for e in body.get("errors", []))
