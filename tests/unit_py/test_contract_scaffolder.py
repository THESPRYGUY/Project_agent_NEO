import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def _run_build(intake: Path, outdir: Path, cwd: Path, env: dict[str, str] | None = None) -> Path:
    envp = dict(os.environ)
    if env:
        envp.update(env)
    cp = subprocess.run(
        [sys.executable, str(cwd / "build_repo.py"), "--intake", str(intake), "--out", str(outdir), "--extend", "--force-utf8", "--emit-parity"],
        cwd=str(cwd), capture_output=True, text=True, env=envp,
    )
    assert cp.returncode == 0, cp.stderr + cp.stdout
    # Slug is agent_id-version where available
    return outdir / "atlas-1-0-0"


def test_scaffolder_adds_required_keys_full_mode(tmp_path: Path) -> None:
    repo_root = Path.cwd()
    intake = tmp_path / "intake.json"
    profile = {
        "agent": {"name": "Atlas Analyst", "version": "1.0.0"},
        "identity": {"agent_id": "atlas", "display_name": "Atlas Analyst", "owners": ["CAIO", "CPA", "TeamLead"]},
        "role_profile": {"role_title": "Enterprise Analyst", "archetype": "AIA-P", "objectives": ["Dashboards"]},
        "sector_profile": {"sector": "Finance", "region": ["NA"], "regulatory": ["SEC"]},
    }
    intake.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    outdir = tmp_path / "out"
    repo_path = _run_build(intake, outdir, repo_root, env={"NEO_CONTRACT_MODE": "full"})

    # Check a couple of files have the 4 required contract keys
    for name in ("02_Global-Instructions_v2.json", "11_Workflow-Pack_v2.json", "14_KPI+Evaluation-Framework_v2.json"):
        d = json.loads((repo_path / name).read_text(encoding="utf-8"))
        assert "meta" in d and isinstance(d["meta"], dict)
        assert "objective" in d
        assert "schema_keys" in d and isinstance(d["schema_keys"], list)
        assert "token_budget" in d and isinstance(d["token_budget"], dict)

    # Integrity report includes contract_ok and missing_keys
    report = json.loads((repo_path / "INTEGRITY_REPORT.json").read_text(encoding="utf-8"))
    assert "contract_ok" in report and isinstance(report["missing_keys"], dict)

