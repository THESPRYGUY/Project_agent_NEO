from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
import io
import zipfile


def _canonical_zip_hash(outdir: Path) -> str:
    excluded_names = {"_last_build.json", ".DS_Store", "contract_report.json"}
    excluded_dirs = {"__pycache__", ".pytest_cache", ".git", "spec_preview"}
    rels = []
    for p in outdir.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(outdir)
        parts = rel.parts
        if any(part.startswith(".") for part in parts):
            continue
        if any(part in excluded_dirs for part in parts):
            continue
        if rel.name in excluded_names:
            continue
        rels.append(rel)
    rels = sorted(rels, key=lambda r: str(r))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in rels:
            data = (outdir / rel).read_bytes()
            info = zipfile.ZipInfo(str(rel).replace("\\", "/"))
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
    import hashlib

    return hashlib.sha256(buf.getvalue()).hexdigest()


def _build_repo(tmp_path: Path) -> Path:
    from neo_build.writers import write_repo_files

    # Force FULL mode for contract completeness
    os.environ["NEO_CONTRACT_MODE"] = "full"
    os.environ["CI"] = "1"

    profile = {
        "identity": {
            "agent_id": "validator-agent",
            "display_name": "Validator Agent",
            "owners": ["CAIO", "CPA", "TeamLead"],
            "no_impersonation": True,
        },
        "role_profile": {
            "archetype": "AIA-P",
            "role_title": "IT Ops Lead",
            "objectives": ["Ship reliably"],
        },
        "sector_profile": {
            "sector": "Technology",
            "industry": "Software",
            "region": ["NA"],
            "regulatory": ["NIST_AI_RMF"],
        },
        "capabilities_tools": {
            "tool_suggestions": ["email"],
            "tool_connectors": [
                {
                    "name": "email",
                    "enabled": True,
                    "scopes": ["read"],
                    "secret_ref": "SET_ME",
                }
            ],
        },
        "memory": {
            "memory_scopes": ["customer"],
            "initial_memory_packs": ["m1"],
            "data_sources": ["kb_main"],
        },
        "governance_eval": {
            "gates": {"PRI_min": 0.95, "hallucination_max": 0.02, "audit_min": 0.9},
            "classification_default": "confidential",
        },
        "preferences": {"sliders": {"autonomy": 70}},
    }
    out_root = tmp_path / "_generated"
    agent_dir = out_root / "validator-agent"
    ts_dir = agent_dir / "20250101T000000Z"
    ts_dir.mkdir(parents=True, exist_ok=True)
    write_repo_files(profile, ts_dir)
    # Write last_build.json in minimal v2.1.1 shape with zip hash
    z = _canonical_zip_hash(ts_dir)
    last = {
        "schema_version": "2.1.1",
        "agent_id": "validator-agent",
        "outdir": str(ts_dir),
        "files": len([p for p in ts_dir.glob("*.json")])
        + len([p for p in ts_dir.glob("*.md")]),
        "ts": ts_dir.name,
        "zip_hash": z,
    }
    (out_root / "_last_build.json").write_text(
        json.dumps(last, indent=2), encoding="utf-8"
    )
    return ts_dir


def test_contract_validate_cli_good(tmp_path: Path) -> None:
    repo_dir = _build_repo(tmp_path)
    cp = subprocess.run(
        [sys.executable, "scripts/contract_validate.py", str(repo_dir)],
        capture_output=True,
        text=True,
    )
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

    cp = subprocess.run(
        [sys.executable, "scripts/contract_validate.py", str(repo_dir)],
        capture_output=True,
        text=True,
    )
    assert cp.returncode != 0, "validator should fail on contract violations"
    data = json.loads(cp.stdout)
    assert data.get("contract_ok") is False
    assert "02_Global-Instructions_v2.json" in data.get("missing_keys", {})
