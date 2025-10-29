import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def _build_full(repo_root: Path, tmp: Path) -> Path:
    intake = tmp / "intake.json"
    outdir = tmp / "out"
    profile = {"identity": {"agent_id": "atlas"}, "agent": {"name": "Atlas", "version": "1.0.0"}}
    intake.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    env = dict(os.environ)
    env["NEO_CONTRACT_MODE"] = "full"
    cp = subprocess.run([sys.executable, str(repo_root / "build_repo.py"), "--intake", str(intake), "--out", str(outdir), "--extend", "--force-utf8", "--emit-parity"], cwd=str(repo_root), capture_output=True, text=True, env=env)
    assert cp.returncode == 0, cp.stderr + cp.stdout
    return outdir / "atlas-1-0-0"


def test_reporting_fields_match_observability_types(tmp_path: Path) -> None:
    repo_root = Path.cwd()
    repo_path = _build_full(repo_root, tmp_path)
    obs = json.loads((repo_path / "15_Observability+Telemetry_Spec_v2.json").read_text(encoding="utf-8"))
    rep = json.loads((repo_path / "18_Reporting-Pack_v2.json").read_text(encoding="utf-8"))
    fields = set(obs.get("decision_event_fields", []))
    types = dict(obs.get("decision_event_field_types", {}))
    assert fields and types
    for tpl in rep.get("templates", []):
        for f in tpl.get("fields", []):
            assert f in fields
            assert types.get(f) in {"string", "number", "boolean"}

