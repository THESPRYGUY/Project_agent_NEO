import json
from pathlib import Path
import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.unit


def test_decision_event_field_types_present_and_canonical(tmp_path: Path) -> None:
    repo_root = Path.cwd()
    intake = tmp_path / "intake.json"
    outdir = tmp_path / "out"
    profile = {"identity": {"agent_id": "atlas"}, "agent": {"name": "Atlas", "version": "1.0.0"}}
    intake.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    env = dict(os.environ)
    env["NEO_CONTRACT_MODE"] = "full"
    cp = subprocess.run([sys.executable, str(repo_root / "build_repo.py"), "--intake", str(intake), "--out", str(outdir), "--extend", "--force-utf8", "--emit-parity"], cwd=str(repo_root), capture_output=True, text=True, env=env)
    assert cp.returncode == 0, cp.stderr + cp.stdout
    repo_path = outdir / "atlas-1-0-0"
    obs = json.loads((repo_path / "15_Observability+Telemetry_Spec_v2.json").read_text(encoding="utf-8"))
    fields = obs.get("decision_event_fields")
    types = obs.get("decision_event_field_types")
    assert isinstance(fields, list) and fields
    assert isinstance(types, dict)
    allowed = {"string", "number", "boolean"}
    for f in fields:
        assert f in types
        assert types[f] in allowed
    # Risk must be numeric
    assert types.get("risk") == "number"

