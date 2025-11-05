from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Any

import sys
from pathlib import Path as _Path

ROOT = _Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neo_build.writers import write_repo_files
from neo_build.validators import integrity_report


def _read(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_parity_hardening_true(tmp_path: Path):
    profile = {
        "identity": {"agent_id": "p4", "display_name": "Parity Agent"},
        "classification": {
            "naics": {"code": "541110", "title": "Offices of Lawyers", "level": 6}
        },
    }
    out = tmp_path / "repo"
    packs = write_repo_files(profile, out)
    report = integrity_report(profile, packs)
    parity = report.get("parity", {})
    assert parity.get("02_vs_14") is True
    assert parity.get("11_vs_02") is True
    assert parity.get("03_vs_02") is True
    assert parity.get("17_vs_02") is True
    assert all(len(v) == 0 for v in (report.get("parity_deltas", {}) or {}).values())


def test_parity_hardening_deltas_from_03(tmp_path: Path):
    profile = {
        "identity": {"agent_id": "p4b", "display_name": "Parity Agent"},
        "classification": {
            "naics": {"code": "541110", "title": "Offices of Lawyers", "level": 6}
        },
    }
    out = tmp_path / "repo2"
    packs = write_repo_files(profile, out)
    # Tweak 03 activation to force mismatch
    p03 = packs.get("03_Operating-Rules_v2.json", {})
    gates = p03.get("gates") or {}
    gates["activation"] = ["PRI>=0.9", "HAL<=0.1", "AUD>=0.8"]
    p03["gates"] = gates
    packs["03_Operating-Rules_v2.json"] = p03

    report = integrity_report(profile, packs)
    parity = report.get("parity", {})
    assert parity.get("03_vs_02") is False
    deltas = (report.get("parity_deltas", {}) or {}).get("03", {})
    assert set(deltas.keys()) == {"PRI_min", "HAL_max", "AUD_min"}
