from __future__ import annotations

import json
import difflib
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.integ


def _run_builder(intake: Path, outdir: Path, cwd: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
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
    )
    assert cp.returncode == 0, cp.stderr + cp.stdout
    # Slug is derived from identity.agent_id + agent.version
    return outdir / "golden-agent-3-0-0"


def _canon(text: str) -> str:
    # Normalize CRLF; strip trailing whitespace/newlines; ensure single trailing \n
    return text.replace("\r\n", "\n").rstrip() + "\n"


def test_golden_snapshot(tmp_path: Path) -> None:
    repo_root = Path.cwd()
    intake = repo_root / "fixtures" / "intake_v3_golden.json"
    expected_dir = repo_root / "fixtures" / "expected_pack_golden"
    assert intake.exists(), "missing golden intake fixture"
    assert expected_dir.exists(), "missing expected pack directory"

    out = tmp_path / "out"
    repo_path = _run_builder(intake, out, repo_root)
    assert repo_path.exists(), f"built repo not found: {repo_path}"

    # Integrity file present and parity all true
    integrity_path = repo_path / "INTEGRITY_REPORT.json"
    assert integrity_path.exists(), "INTEGRITY_REPORT.json not found"
    integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
    errors = list(integrity.get("errors", []) or [])
    assert len(errors) == 0, f"integrity errors present: {errors}"
    parity = dict(integrity.get("parity") or {})
    assert all(parity.get(k) is True for k in ("02_vs_14", "11_vs_02", "03_vs_02", "17_vs_02")), f"parity not ALL_TRUE: {parity}"

    # Canonical 20 files present and identical to snapshot (normalized newlines)
    from neo_build.contracts import CANONICAL_PACK_FILENAMES

    artifacts = repo_root / "_artifacts" / "golden-diff"
    artifacts.mkdir(parents=True, exist_ok=True)

    first_diff: str | None = None
    for name in CANONICAL_PACK_FILENAMES:
        got_path = repo_path / name
        exp_path = expected_dir / name
        assert got_path.exists(), f"missing built file: {name}"
        assert exp_path.exists(), f"missing expected file: {name}"
        got = _canon(got_path.read_text(encoding="utf-8"))
        exp = _canon(exp_path.read_text(encoding="utf-8"))
        if got != exp:
            # Write a small diff file and record the first mismatch
            diff = difflib.unified_diff(
                exp.splitlines(keepends=True),
                got.splitlines(keepends=True),
                fromfile=f"expected/{name}",
                tofile=f"built/{name}",
            )
            diff_text = "".join(diff)
            (artifacts / f"{name}.diff").write_text(diff_text, encoding="utf-8")
            if first_diff is None:
                first_diff = name

    if first_diff is not None:
        pytest.fail(f"Golden snapshot drift detected in {first_diff}; see _artifacts/golden-diff")
