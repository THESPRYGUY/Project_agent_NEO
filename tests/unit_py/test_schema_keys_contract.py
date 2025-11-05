import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from neo_build.contracts import CANONICAL_PACK_FILENAMES
from neo_build.schemas import required_keys_map

pytestmark = pytest.mark.unit


def _run_build(
    intake: Path, outdir: Path, cwd: Path, env: dict[str, str] | None = None
) -> Path:
    envp = dict(os.environ)
    if env:
        envp.update(env)
    # Minimal valid profile
    profile = {
        "agent": {"name": "Atlas Analyst", "version": "1.0.0"},
        "identity": {
            "agent_id": "atlas",
            "display_name": "Atlas Analyst",
            "owners": ["CAIO", "CPA", "TeamLead"],
        },
        "role_profile": {
            "role_title": "Enterprise Analyst",
            "archetype": "AIA-P",
            "objectives": ["Dashboards"],
        },
        "sector_profile": {
            "sector": "Finance",
            "region": ["NA"],
            "regulatory": ["SEC"],
        },
    }
    intake.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    cp = subprocess.run(
        [
            sys.executable,
            str(cwd / "build_repo.py"),
            "--intake",
            str(intake),
            "--out",
            str(outdir),
            "--extend",
            "--force-utf8",
            "--emit-parity",
        ],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=envp,
    )
    assert cp.returncode == 0, cp.stderr + cp.stdout
    return outdir / "atlas-1-0-0"


def test_schema_keys_exact_and_sorted(tmp_path: Path) -> None:
    repo_root = Path.cwd()
    outdir = tmp_path / "out"
    outdir.mkdir(parents=True, exist_ok=True)
    intake = tmp_path / "intake.json"
    repo_path = _run_build(intake, outdir, repo_root, env={"NEO_CONTRACT_MODE": "full"})

    req_map = required_keys_map()
    for fname in CANONICAL_PACK_FILENAMES:
        data = json.loads((repo_path / fname).read_text(encoding="utf-8"))
        got = data.get("schema_keys")
        assert isinstance(got, list)
        expect = sorted(set(req_map.get(fname, [])))
        assert got == expect
