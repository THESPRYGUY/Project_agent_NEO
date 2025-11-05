import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_contract_check_cli_detects_missing(tmp_path: Path) -> None:
    packs_dir = tmp_path / "packs"
    packs_dir.mkdir(parents=True, exist_ok=True)
    # Write a single file with missing keys
    (packs_dir / "01_README+Directory-Map_v2.json").write_text(
        json.dumps({"meta": {}}, indent=2), encoding="utf-8"
    )

    cp = subprocess.run(
        [sys.executable, "scripts/contract_check.py", str(packs_dir)],
        capture_output=True,
        text=True,
    )
    # Should be non-zero due to missing keys in many files
    assert cp.returncode != 0
    out = json.loads(cp.stdout)
    assert out.get("contract_ok") is False
    assert isinstance(out.get("missing_keys"), dict)
