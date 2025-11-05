import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_integrity_report_flags_full_mode(tmp_path: Path) -> None:
    repo_root = Path.cwd()
    intake = tmp_path / "intake.json"
    outdir = tmp_path / "out"
    profile = {
        "identity": {"agent_id": "atlas"},
        "agent": {"name": "Atlas", "version": "1.0.0"},
    }
    intake.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    env = dict(os.environ)
    env["NEO_CONTRACT_MODE"] = "full"
    cp = subprocess.run(
        [
            sys.executable,
            str(repo_root / "build_repo.py"),
            "--intake",
            str(intake),
            "--out",
            str(outdir),
            "--extend",
            "--force-utf8",
            "--emit-parity",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=env,
    )
    assert cp.returncode == 0, cp.stderr + cp.stdout
    repo_path = outdir / "atlas-1-0-0"
    ir = json.loads((repo_path / "INTEGRITY_REPORT.json").read_text(encoding="utf-8"))
    # New flags present
    assert ir.get("packs_complete") is True
    assert isinstance(ir.get("missing_sections"), dict)
    assert ir.get("missing_sections") == {}
    # Existing flags remain
    assert ir.get("contract_ok") is True
    assert ir.get("crossref_ok") in (True, False)  # present
    assert isinstance(ir.get("parity_ok"), bool)
