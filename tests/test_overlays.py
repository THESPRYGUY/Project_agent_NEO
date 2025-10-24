from __future__ import annotations

import json
from pathlib import Path

from neo_build.overlays import apply_overlays, load_overlay_config
from neo_build.validators import integrity_report
from neo_agent.intake_app import create_app
import yaml


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


def test_disallowed_key_is_skipped(tmp_path: Path):
    app = create_app(base_dir=tmp_path)
    st, _, body = _wsgi_call(app, "POST", "/save", _profile())
    assert st == "200 OK", body
    st, _, body = _wsgi_call(app, "POST", "/build", {})
    assert st == "200 OK", body
    out = json.loads(body.decode("utf-8"))
    outdir = Path(out["outdir"]).resolve()
    # Build a custom ops YAML that tries to touch a disallowed key
    ops = {
        "operations": [
            {"upsert": {"target_file": "11_Workflow-Pack_v2.json", "set": {"not_allowed": {"x": 1}}}},
        ]
    }
    custom_yaml = tmp_path / "ops.yaml"
    custom_yaml.write_text(yaml.safe_dump(ops), encoding="utf-8")
    cfg = {"apply": ["persistence_adaptiveness"], "persistence_ops": str(custom_yaml)}
    summary = apply_overlays(outdir, cfg)
    assert any(s.startswith("11_Workflow-Pack_v2.json:not_allowed") for s in summary.get("skipped", []))


def test_atomic_rollback_restores_repo_on_failure(tmp_path: Path):
    # Create repo
    app = create_app(base_dir=tmp_path)
    st, _, body = _wsgi_call(app, "POST", "/save", _profile())
    assert st == "200 OK", body
    st, _, body = _wsgi_call(app, "POST", "/build", {})
    assert st == "200 OK", body
    out = json.loads(body.decode("utf-8"))
    outdir = Path(out["outdir"]).resolve()
    # Break parity intentionally by modifying 14.targets
    k14 = outdir / "14_KPI+Evaluation-Framework_v2.json"
    data = json.loads(k14.read_text(encoding="utf-8"))
    data.setdefault("targets", {})["PRI_min"] = 0.1
    k14.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # Apply overlays which will not fix parity; expect rollback
    cfg = load_overlay_config()
    summary = apply_overlays(outdir, cfg)
    assert summary.get("rolled_back") is True
    # Since overlays add approvals to 11, ensure it's not present after rollback
    wf = json.loads((outdir / "11_Workflow-Pack_v2.json").read_text(encoding="utf-8"))
    assert "approvals" not in wf or not wf.get("approvals")
