from __future__ import annotations

import io
import json
from pathlib import Path

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


def _profile():
    return {
        "intake_version": "v3.0",
        "identity": {
            "agent_id": "AGENT-TST-001",
            "display_name": "Test Agent",
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


def test_build_route(tmp_path: Path, monkeypatch):
    app = create_app(base_dir=tmp_path)
    # Save v3 profile
    status, _, body = _call(app, "POST", "/save", _profile())
    assert status == "200 OK", body
    # Ensure a local outdir (non-OneDrive) is used
    gen_root = tmp_path / "_generated"
    monkeypatch.setenv("NEO_REPO_OUTDIR", str(gen_root))
    # Build
    status, _, body = _call(app, "POST", "/build", {})
    assert status == "200 OK", body
    out = json.loads(body.decode("utf-8"))
    outdir = Path(out["outdir"])
    assert outdir.exists()
    # Check required files
    for name in [
        "01_README+Directory-Map_v2.json",
        "02_Global-Instructions_v2.json",
        "11_Workflow-Pack_v2.json",
        "14_KPI+Evaluation-Framework_v2.json",
        "INTEGRITY_REPORT.json",
    ]:
        assert (outdir / name).exists(), f"missing {name}"
    # Parity flags
    assert out["parity"]["02_vs_14"] is True
    assert out["parity"]["11_vs_02"] is True
