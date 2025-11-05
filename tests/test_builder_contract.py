from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(cwd / "build_repo.py"), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def test_cli_flags_and_canonical_list(tmp_path: Path) -> None:
    repo_root = Path.cwd()
    # Prepare minimal intake file
    intake = tmp_path / "profile.json"
    intake.write_text(
        json.dumps({"agent": {"name": "X", "version": "1"}}, indent=2), encoding="utf-8"
    )
    outdir = tmp_path / "out"
    cp = run_cli(
        [
            "--intake",
            str(intake),
            "--out",
            str(outdir),
            "--extend",
            "--verbose",
            "--strict",
            "--force-utf8",
            "--emit-parity",
        ],
        repo_root,
    )
    assert cp.returncode == 0, cp.stderr + cp.stdout
    # Check artifact list
    created = sorted(p.name for p in (outdir / "x-1").iterdir())
    assert "neo_agent_config.json" in created
    assert "Agent_Manifest.json" in created
    assert "INTEGRITY_REPORT.json" in created
