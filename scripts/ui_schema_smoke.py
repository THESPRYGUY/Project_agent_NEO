from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mapper import apply_intake
from neo_agent.intake_app import IntakeApplication


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    app = IntakeApplication()
    schema = app._intake_schema_payload()
    sample = schema.get("sample") or {}
    payload = json.loads(json.dumps(sample)) if sample else {}
    payload.setdefault("metadata", {})["submitted_at"] = _iso_now()
    payload.setdefault("governance", {})["risk_register_tags"] = ['ci_smoke_guard']
    build_root = getattr(app, "_default_build_root", None)
    if build_root is None:
        build_root = Path(app.project_root) / "generated_repos" / "agent-build-007-2-1-1"
    result = apply_intake(payload, build_root, dry_run=True)
    mapping = result.get("mapping_report") or []
    diff = result.get("diff_report") or []
    changed = result.get("changed_files") or []
    if not mapping or not diff:
        raise SystemExit("ui-schema-smoke: expected non-empty mapping and diff report")
    print(f"ui-schema-smoke: dry-run ok | mappings={len(mapping)} diff_packs={len(diff)} changed={len(changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
