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
    profile = {
        "agent": {"name": "Atlas Analyst", "version": "1.0.0"},
        "identity": {"agent_id": "atlas"},
        "capabilities_tools": {
            "tool_suggestions": ["email", "calendar"],
            "human_gate": {"actions": ["legal_advice"]},
        },
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
    return outdir / "atlas-1-0-0"


def test_workflow_nodes_reference_prompt_modules(tmp_path: Path) -> None:
    repo_root = Path.cwd()
    repo_path = _build_full(repo_root, tmp_path)
    p10 = json.loads((repo_path / "10_Prompt-Pack_v2.json").read_text(encoding="utf-8"))
    p11 = json.loads(
        (repo_path / "11_Workflow-Pack_v2.json").read_text(encoding="utf-8")
    )
    mods = {m.get("id") for m in p10.get("modules", [])}
    assert mods, "Expected modules in 10_Prompt-Pack_v2.json"
    for g in p11.get("graphs", []):
        for n in g.get("nodes", []):
            mid = n.get("module_id")
            assert mid in mods, f"Workflow node references unknown module_id: {mid}"
