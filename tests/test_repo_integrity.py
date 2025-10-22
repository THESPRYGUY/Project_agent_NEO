from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from neo_build.contracts import CANONICAL_PACK_FILENAMES, KPI_TARGETS, REQUIRED_ALERTS, REQUIRED_EVENTS, REQUIRED_HUMAN_GATE_ACTIONS


def _run_build(intake: Path, outdir: Path, cwd: Path) -> Path:
    cp = subprocess.run([sys.executable, str(cwd / "build_repo.py"), "--intake", str(intake), "--out", str(outdir), "--extend", "--verbose", "--force-utf8", "--emit-parity"], cwd=str(cwd), capture_output=True, text=True)
    assert cp.returncode == 0, cp.stderr + cp.stdout
    # Builder uses identity.agent_id when present
    return outdir / "atlas-1-0-0"


def test_20_pack_presence_and_integrity(tmp_path: Path) -> None:
    repo_root = Path.cwd()
    intake = tmp_path / "intake.json"
    profile = {
        "agent": {"name": "Atlas Analyst", "version": "1.0.0"},
        "preferences": {"sliders": {"autonomy": 80}},
        "identity": {"agent_id": "atlas", "display_name": "Atlas Analyst", "no_impersonation": True},
        "role_profile": {"role_title": "Enterprise Analyst", "role_recipe_ref": "RR-001", "objectives": ["Dashboards"]},
        "sector_profile": {"sector": "Finance", "region": ["NA"], "regulatory": ["SEC"]},
        "capabilities_tools": {"tool_connectors": [{"name": "clm", "enabled": True, "scopes": ["read"], "secret_ref": "SET_ME"}], "human_gate": {"actions": ["legal_advice"]}},
        "memory": {"memory_scopes": ["customer"], "initial_memory_packs": ["m1"], "optional_packs": [], "data_sources": ["kb_main"]},
        "governance_eval": {"risk_register_tags": ["gdpr"], "pii_flags": ["email"], "classification_default": "confidential"},
        "classification": {"naics": {"code": "541", "title": "Professional, Scientific, and Technical Services", "level": 3, "lineage": [{"code": "54", "title": "Professional, Scientific, and Technical Services", "level": 2}]}},
    }
    intake.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    outdir = tmp_path / "out"
    repo_path = _run_build(intake, outdir, repo_root)

    # Canonical files
    for name in CANONICAL_PACK_FILENAMES:
        assert (repo_path / name).exists(), f"Missing {name}"
    assert (repo_path / "README.md").exists()
    assert (repo_path / "neo_agent_config.json").exists()
    assert (repo_path / "build_log.md").exists()

    # KPI sync 11/14/17
    k11 = json.loads((repo_path / "11_Workflow-Pack_v2.json").read_text(encoding="utf-8")).get("gates", {}).get("kpi_targets")
    k14 = json.loads((repo_path / "14_KPI+Evaluation-Framework_v2.json").read_text(encoding="utf-8")).get("targets")
    k17 = json.loads((repo_path / "17_Lifecycle-Pack_v2.json").read_text(encoding="utf-8")).get("gates", {}).get("kpi_targets")
    assert k11 == KPI_TARGETS == k14 == k17

    # Observability
    obs = json.loads((repo_path / "15_Observability+Telemetry_Spec_v2.json").read_text(encoding="utf-8"))
    assert set(REQUIRED_EVENTS).issubset(set(obs.get("events", [])))
    assert set(REQUIRED_ALERTS).issubset(set(obs.get("alerts", [])))

    # Human gate actions include required
    rules = json.loads((repo_path / "03_Operating-Rules_v2.json").read_text(encoding="utf-8"))
    actions = rules.get("human_gate", {}).get("actions", [])
    for req in REQUIRED_HUMAN_GATE_ACTIONS:
        assert req in actions

    # Effective autonomy persisted
    effective = json.loads((repo_path / "11_Workflow-Pack_v2.json").read_text(encoding="utf-8")).get("gates", {}).get("effective_autonomy")
    assert 0 < effective <= 0.28

    # 01 narrative + README header
    readme_map = json.loads((repo_path / "01_README+Directory-Map_v2.json").read_text(encoding="utf-8"))
    assert isinstance(readme_map.get("files"), list)
    readme_txt = (repo_path / "README.md").read_text(encoding="utf-8")
    assert "Directory Map & Narrative" in readme_txt

    # Connectors alias mapping applied
    reg = json.loads((repo_path / "12_Tool+Data-Registry_v2.json").read_text(encoding="utf-8"))
    names = [c.get("name") for c in reg.get("connectors", [])]
    assert "sharepoint" in names
