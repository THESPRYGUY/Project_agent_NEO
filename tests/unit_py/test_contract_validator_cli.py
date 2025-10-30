from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _build_repo(tmp_path: Path) -> Path:
    from neo_build.writers import write_repo_files
    # Force FULL mode for contract completeness
    os.environ["NEO_CONTRACT_MODE"] = "full"
    os.environ["CI"] = "1"

    profile = {
        "identity": {"agent_id": "validator-agent", "display_name": "Validator Agent", "owners": ["CAIO", "CPA", "TeamLead"], "no_impersonation": True},
        "role_profile": {"archetype": "AIA-P", "role_title": "IT Ops Lead", "objectives": ["Ship reliably"]},
        "sector_profile": {"sector": "Technology", "industry": "Software", "region": ["NA"], "regulatory": ["NIST_AI_RMF"]},
        "capabilities_tools": {"tool_suggestions": ["email"], "tool_connectors": [{"name": "email", "enabled": True, "scopes": ["read"], "secret_ref": "SET_ME"}]},
        "memory": {"memory_scopes": ["customer"], "initial_memory_packs": ["m1"], "data_sources": ["kb_main"]},
        "governance_eval": {"gates": {"PRI_min": 0.95, "hallucination_max": 0.02, "audit_min": 0.9}, "classification_default": "confidential"},
        "preferences": {"sliders": {"autonomy": 70}},
    }
    outdir = tmp_path / "repo"
    outdir.mkdir(parents=True, exist_ok=True)
    write_repo_files(profile, outdir)
    return outdir


def test_contract_validate_cli_good(tmp_path: Path) -> None:
    repo_dir = _build_repo(tmp_path)
    cp = subprocess.run([sys.executable, "scripts/contract_validate.py", str(repo_dir)], capture_output=True, text=True)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    data = json.loads(cp.stdout)
    assert data.get("contract_ok") is True
    assert data.get("crossref_ok") is True
    assert data.get("parity_ok") is True
    assert data.get("packs_complete") is True


def test_contract_validate_cli_bad(tmp_path: Path) -> None:
    repo_dir = _build_repo(tmp_path)
    # Remove a required key from 02 to trigger failures
    path_02 = repo_dir / "02_Global-Instructions_v2.json"
    obj = json.loads(path_02.read_text(encoding="utf-8"))
    if "constraints" in obj:
        del obj["constraints"]
    path_02.write_text(json.dumps(obj, indent=2), encoding="utf-8")

    cp = subprocess.run([sys.executable, "scripts/contract_validate.py", str(repo_dir)], capture_output=True, text=True)
    assert cp.returncode != 0, "validator should fail on contract violations"
    data = json.loads(cp.stdout)
    assert data.get("contract_ok") is False
    assert "02_Global-Instructions_v2.json" in data.get("missing_keys", {})

