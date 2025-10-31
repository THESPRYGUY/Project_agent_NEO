import json
import os
import subprocess
from pathlib import Path

import pytest


def test_golden_snapshot_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo_root = Path(__file__).resolve().parents[2]
    intake = repo_root / "fixtures" / "intake_v3_golden.json"
    assert intake.exists(), f"missing intake fixture: {intake}"

    out_base = tmp_path / "_generated"
    out_base.mkdir(parents=True, exist_ok=True)

    # Ensure FULL mode and stable env
    monkeypatch.setenv("NEO_CONTRACT_MODE", "full")
    monkeypatch.setenv("PYTHONPATH", str(repo_root / "src"))

    # Build repo via CLI to mirror CI behavior
    cmd = [
        "python",
        str(repo_root / "build_repo.py"),
        "--intake",
        str(intake),
        "--out",
        str(out_base),
        "--extend",
        "--force-utf8",
        "--emit-parity",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"build_repo failed: {res.stderr or res.stdout}"

    # Golden slug location
    outdir = out_base / "golden-agent-3-0-0"
    assert outdir.exists(), f"expected outdir not found: {outdir}"

    # Verify canonical files count (20)
    from neo_build.contracts import CANONICAL_PACK_FILENAMES

    present = [name for name in CANONICAL_PACK_FILENAMES if (outdir / name).exists()]
    assert len(present) == 20, f"expected 20 canonical files, got {len(present)}"

    # Integrity report presence and basic gates
    ir = outdir / "INTEGRITY_REPORT.json"
    assert ir.exists(), "INTEGRITY_REPORT.json missing"
    obj = json.loads(ir.read_text(encoding="utf-8"))
    assert obj.get("contract_ok") is True, "contract_ok false"
    assert obj.get("parity_ok") is True, "parity_ok false"
    assert obj.get("packs_complete") is True, "packs_complete false"

