from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from mapper import apply_intake
from neo_agent.intake_app import IntakeApplication


def test_ui_payload_roundtrip(tmp_path):
    app = IntakeApplication(base_dir=tmp_path)
    schema = app._intake_schema_payload()
    defaults = schema.get("defaults", {})
    assert defaults.get("connectors"), "expected connectors in defaults"
    sample = schema.get("sample") or {}
    assert sample.get("intake_version") == "v1"
    payload = json.loads(json.dumps(sample))
    payload.setdefault("metadata", {})["submitted_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    build_root = getattr(app, "_default_build_root", None)
    if build_root is None:
        build_root = Path(app.project_root) / "generated_repos" / "agent-build-007-2-1-1"
    result = apply_intake(payload, build_root, dry_run=True)
    assert isinstance(result.get("mapping_report"), list)
    assert isinstance(result.get('diff_report'), list)
    assert isinstance(result.get('changed_files'), list)
    assert result.get('dry_run') is True
