from __future__ import annotations

import io
import json
import os
from pathlib import Path
import pytest


pytestmark = pytest.mark.integ


def _ensure_import() -> None:
    import sys

    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _call(app, method: str, path: str, body: dict | None = None):
    raw = json.dumps(body or {}).encode("utf-8")
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "integ",
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


def test_legacy_only_payload_builds_ok(tmp_path: Path, monkeypatch):
    _ensure_import()
    from neo_build.adapters.legacy_to_v3 import transform
    from neo_agent.intake_app import create_app

    app = create_app(base_dir=tmp_path)

    # Start with a legacy-only payload (plus identity)
    legacy_only = {
        "identity": {
            "agent_id": "AGT-LEG-001",
            "display_name": "Legacy Agent",
            "owners": ["CAIO"],
        },
        "legacy": {
            "role": "AIA-P",
            "kpi": {"PRI_min": 0.95, "HAL_max": 0.02, "AUD_min": 0.9},
        },
    }

    # Adapter migration
    v3, _diag = transform(legacy_only)
    # Minimal required v3 fields to pass /save schema
    v3.setdefault("identity", legacy_only["identity"])  # ensure identity present
    v3["context"] = {"naics": {"code": "541110"}, "region": ["CA"]}
    role = dict(v3.get("role") or {})
    role.setdefault("function_code", "legal_compliance")
    v3["role"] = role

    # Save v3 and build
    st, _, raw = _call(app, "POST", "/save", v3)
    assert st.startswith("200"), raw

    # Ensure local outdir to avoid OneDrive path effects
    monkeypatch.setenv("NEO_REPO_OUTDIR", str(tmp_path / "_generated"))
    st, _, raw = _call(app, "POST", "/build", {})
    assert st.startswith("200"), raw
    out = json.loads(raw.decode("utf-8"))
    outdir = Path(out["outdir"])
    assert outdir.exists()
    # core files and parity
    for name in [
        "01_README+Directory-Map_v2.json",
        "02_Global-Instructions_v2.json",
        "11_Workflow-Pack_v2.json",
        "14_KPI+Evaluation-Framework_v2.json",
        "INTEGRITY_REPORT.json",
    ]:
        assert (outdir / name).exists(), f"missing {name}"
    assert out["parity"]["02_vs_14"] is True
    assert out["parity"]["11_vs_02"] is True


def test_mixed_legacy_v3_rejected(tmp_path: Path):
    _ensure_import()
    from neo_agent.intake_app import create_app

    app = create_app(base_dir=tmp_path)

    payload = {
        "intake_version": "v3.0",
        "identity": {"agent_id": "X", "display_name": "X", "owners": ["CAIO"]},
        "context": {"naics": {"code": "541110"}},
        "role": {"function_code": "fn", "role_code": "rc"},
        "governance_eval": {
            "gates": {"PRI_min": 0.95, "hallucination_max": 0.02, "audit_min": 0.9}
        },
        "legacy": {"role": "OLD"},
    }
    st, _, raw = _call(app, "POST", "/save", payload)
    assert st.startswith("400")
    body = json.loads(raw.decode("utf-8"))
    assert body.get("code") == "DUPLICATE_LEGACY_V3_CONFLICT"


def test_adapter_does_not_mutate_input():
    _ensure_import()
    from neo_build.adapters.legacy_to_v3 import transform

    legacy_payload = {
        "identity": {
            "agent_id": "AG-1",
            "display_name": "Agent One",
            "owners": ["CAIO"],
        },
        "legacy": {"role": "AIA-P", "kpi": {"PRI_min": 0.95}},
    }
    # Keep a copy for comparison
    import copy

    original = copy.deepcopy(legacy_payload)
    _v3, _diag = transform(legacy_payload)
    assert legacy_payload == original, "transform mutated legacy input"
