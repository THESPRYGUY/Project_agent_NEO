import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from neo_build.contracts import PACK_ID_TO_FILENAME

pytestmark = pytest.mark.unit


def _build_full(repo_root: Path, tmp: Path) -> Path:
    intake = tmp / "intake.json"
    outdir = tmp / "out"
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
            "languages": ["en"],
        },
        "capabilities_tools": {"human_gate": {"actions": ["legal_advice"]}},
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


def test_crossrefs_from_02(tmp_path: Path) -> None:
    repo_root = Path.cwd()
    repo_path = _build_full(repo_root, tmp_path)
    gi = json.loads((repo_path / PACK_ID_TO_FILENAME[2]).read_text(encoding="utf-8"))
    # 8 cross-file links
    assert gi["constraints"]["governance_file"] == PACK_ID_TO_FILENAME[4]
    assert gi["constraints"]["safety_privacy_file"] == PACK_ID_TO_FILENAME[5]
    assert gi["constraints"]["eval_framework_file"] == PACK_ID_TO_FILENAME[14]
    assert gi["constraints"]["observability_file"] == PACK_ID_TO_FILENAME[15]
    assert gi["agentic_policies"]["routing"]["workflow_pack"] == PACK_ID_TO_FILENAME[11]
    assert gi["agentic_policies"]["routing"]["prompt_pack"] == PACK_ID_TO_FILENAME[10]
    assert (
        gi["agentic_policies"]["reasoning"]["footprints_spec"]
        == PACK_ID_TO_FILENAME[16]
    )
    assert gi["go_live"]["lifecycle_pack"] == PACK_ID_TO_FILENAME[17]

    # Integrity report crossref_ok
    ir = json.loads((repo_path / "INTEGRITY_REPORT.json").read_text(encoding="utf-8"))
    assert ir.get("crossref_ok") is True
    assert ir.get("parity_ok") is True


def test_parity_02_vs_14_and_11_vs_02(tmp_path: Path) -> None:
    repo_root = Path.cwd()
    repo_path = _build_full(repo_root, tmp_path)
    p02 = json.loads((repo_path / PACK_ID_TO_FILENAME[2]).read_text(encoding="utf-8"))
    p14 = json.loads((repo_path / PACK_ID_TO_FILENAME[14]).read_text(encoding="utf-8"))
    p11 = json.loads((repo_path / PACK_ID_TO_FILENAME[11]).read_text(encoding="utf-8"))
    targets_02 = (p02.get("observability") or {}).get("kpi_targets")
    assert targets_02 and isinstance(targets_02, dict)
    assert p14.get("targets") == targets_02
    gates_11 = p11.get("gates") or {}
    # Allow synonyms but our builder uses canonical keys
    k11 = gates_11.get("kpi_targets") or {
        "PRI_min": gates_11.get("PRI_min"),
        "HAL_max": gates_11.get("hallucination_max"),
        "AUD_min": gates_11.get("audit_min"),
    }
    assert k11 == targets_02
