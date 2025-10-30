import json
from pathlib import Path
import os
import subprocess
import sys

import pytest

from neo_build.validators import integrity_report

pytestmark = pytest.mark.unit


def test_validator_flags_secret_values(tmp_path: Path) -> None:
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

    # Load packs and inject an invalid secret value
    packs = {}
    for p in repo_path.iterdir():
        if p.suffix == ".json" and p.name != "INTEGRITY_REPORT.json":
            packs[p.name] = json.loads(p.read_text(encoding="utf-8"))
    p12 = packs.get("12_Tool+Data-Registry_v2.json")
    assert p12 is not None
    secrets = p12.get("secrets") or []
    secrets.append({"name": "email", "value": "DONTSTORE"})
    p12["secrets"] = secrets

    report = integrity_report({}, packs)
    assert any("secrets must not include values" in e for e in report.get("errors", []))

