from __future__ import annotations

import json
from pathlib import Path

from neo_build.overlays import apply_overlays, load_overlay_config
from neo_build.validators import integrity_report
from neo_agent.intake_app import create_app


def _wsgi_call(app, method: str, path: str, body: dict | None = None):
    import io
    raw = json.dumps(body or {}).encode("utf-8")
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "test",
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


def _profile() -> dict:
    return {
        "intake_version": "v3.0",
        "identity": {"agent_id": "AGENT-OL-001", "display_name": "Overlay Agent", "owners": ["Owner"]},
        "context": {"naics": {"code": "541512"}, "region": ["CA"]},
        "role": {"function_code": "it_ops", "role_code": "AIA-P", "role_title": "Lead"},
        "governance_eval": {"gates": {"PRI_min": 0.95, "hallucination_max": 0.02, "audit_min": 0.9}},
    }


def test_overlays_noop_19_20(tmp_path: Path, monkeypatch):
    app = create_app(base_dir=tmp_path)
    st, _, body = _wsgi_call(app, "POST", "/save", _profile())
    assert st == "200 OK", body
    st, _, body = _wsgi_call(app, "POST", "/build", {})
    assert st == "200 OK", body
    out = json.loads(body.decode("utf-8"))
    outdir = Path(out["outdir"]).resolve()
    assert outdir.exists()
    cfg = {"apply": ["19_SME_Domain", "20_Enterprise"]}
    summary = apply_overlays(outdir, cfg)
    # SME/Enterprise overlays should be no-op by default for generated packs
    assert "19_SME_Domain" in summary["applied"] and "20_Enterprise" in summary["applied"]
    assert summary["integrity_errors"] == []
    # Parity remains true
    p = summary.get("parity") or {}
    assert all(p.get(k, True) for k in ("02_vs_14", "11_vs_02", "03_vs_02", "17_vs_02"))


def test_persistence_adaptiveness_applies_and_keeps_parity(tmp_path: Path):
    app = create_app(base_dir=tmp_path)
    st, _, body = _wsgi_call(app, "POST", "/save", _profile())
    assert st == "200 OK", body
    st, _, body = _wsgi_call(app, "POST", "/build", {})
    assert st == "200 OK", body
    out = json.loads(body.decode("utf-8"))
    outdir = Path(out["outdir"]).resolve()
    cfg = load_overlay_config()
    cfg["apply"] = ["persistence_adaptiveness"]
    summary = apply_overlays(outdir, cfg)
    assert "persistence_adaptiveness" in summary["applied"]
    assert summary["integrity_errors"] == []
    p = summary.get("parity") or {}
    assert all(p.get(k, True) for k in ("02_vs_14", "11_vs_02", "03_vs_02", "17_vs_02"))
    # Spot-check a couple of fields were added
    wf = json.loads((outdir / "11_Workflow-Pack_v2.json").read_text(encoding="utf-8"))
    op = json.loads((outdir / "03_Operating-Rules_v2.json").read_text(encoding="utf-8"))
    assert "approvals" in wf and "escalation_flow" in wf
    assert "stop_conditions" in op and "persistence_formula" in op

