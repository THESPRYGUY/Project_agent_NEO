from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Iterable


def _canonical_zip_hash(outdir: Path, *, exclude_names: set[str] | None = None, exclude_dirs: set[str] | None = None) -> str:
    exclude_names = exclude_names or {"_last_build.json", ".DS_Store", "contract_report.json"}
    exclude_dirs = exclude_dirs or {"__pycache__", ".pytest_cache", ".git", "spec_preview"}
    rels: list[Path] = []
    for p in outdir.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(outdir)
        parts = rel.parts
        if any(part.startswith(".") for part in parts):
            continue
        if any(part in exclude_dirs for part in parts):
            continue
        if rel.name in exclude_names:
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


def _write_last_build(out_root: Path, outdir: Path, zip_hash: str) -> None:
    obj = {
        "schema_version": "2.1.1",
        "agent_id": "TEST-AGENT",
        "outdir": str(outdir),
        "files": len([p for p in outdir.glob("*.json")]) + len([p for p in outdir.glob("*.md")]),
        "ts": outdir.name,
        "zip_hash": zip_hash,
    }
    (out_root / "_last_build.json").write_text(json.dumps(obj, indent=2), encoding="utf-8")


def test_schema_v211_required_keys(tmp_path: Path, monkeypatch) -> None:
    # Build into SoT layout: _generated/<AGENT>/<TS>
    from neo_build.writers import write_repo_files

    out_root = tmp_path / "_generated"
    agent_dir = out_root / "TEST-AGENT"
    ts_dir = agent_dir / "20250101T000000Z"
    ts_dir.mkdir(parents=True, exist_ok=True)

    profile = {
        "identity": {"agent_id": "TEST-AGENT", "display_name": "Validator Agent", "owners": ["Owner"], "no_impersonation": True},
        "role_profile": {"archetype": "AIA-P", "role_title": "IT Ops Lead", "objectives": ["Ship reliably"]},
        "sector_profile": {"sector": "Technology", "industry": "Software", "region": ["NA"], "regulatory": ["NIST_AI_RMF"]},
        "capabilities_tools": {"tool_suggestions": ["email"], "tool_connectors": [{"name": "email", "enabled": True, "scopes": ["read"], "secret_ref": "SET_ME"}]},
        "memory": {"memory_scopes": ["customer"], "initial_memory_packs": ["m1"], "data_sources": ["kb_main"]},
        "governance_eval": {"gates": {"PRI_min": 0.95, "hallucination_max": 0.02, "audit_min": 0.9}, "classification_default": "confidential"},
    }
    write_repo_files(profile, ts_dir)

    z = _canonical_zip_hash(ts_dir)
    _write_last_build(out_root, ts_dir, z)

    # Run validator CLI and assert pass
    cp = subprocess.run([sys.executable, "scripts/contract_validate.py", str(ts_dir)], capture_output=True, text=True)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    data = json.loads(cp.stdout)
    keys = set(json.loads((out_root / "_last_build.json").read_text()).keys())
    assert {"schema_version", "agent_id", "outdir", "files", "ts", "zip_hash"}.issubset(keys)
    assert data.get("last_build_schema_ok") is True
    assert data.get("zip_hash_match") is True


def test_validator_fails_on_pre211_shape(tmp_path: Path, monkeypatch) -> None:
    from neo_build.writers import write_repo_files

    out_root = tmp_path / "_generated"
    agent_dir = out_root / "TEST-AGENT"
    ts_dir = agent_dir / "20250101T000000Z"
    ts_dir.mkdir(parents=True, exist_ok=True)

    profile = {
        "identity": {"agent_id": "TEST-AGENT", "display_name": "Validator Agent", "owners": ["Owner"], "no_impersonation": True},
        "role_profile": {"archetype": "AIA-P", "role_title": "IT Ops Lead", "objectives": ["Ship reliably"]},
        "sector_profile": {"sector": "Technology", "industry": "Software", "region": ["NA"], "regulatory": ["NIST_AI_RMF"]},
        "capabilities_tools": {"tool_suggestions": ["email"], "tool_connectors": [{"name": "email", "enabled": True, "scopes": ["read"], "secret_ref": "SET_ME"}]},
        "memory": {"memory_scopes": ["customer"], "initial_memory_packs": ["m1"], "data_sources": ["kb_main"]},
        "governance_eval": {"gates": {"PRI_min": 0.95, "hallucination_max": 0.02, "audit_min": 0.9}, "classification_default": "confidential"},
    }
    write_repo_files(profile, ts_dir)

    # Intentionally write an old/invalid _last_build.json (missing zip_hash, old version)
    bad = {
        "timestamp": "2025-01-01T00:00:00Z",
        "outdir": str(ts_dir),
        "file_count": 20,
    }
    (out_root / "_last_build.json").write_text(json.dumps(bad, indent=2), encoding="utf-8")

    cp = subprocess.run([sys.executable, "scripts/contract_validate.py", str(ts_dir)], capture_output=True, text=True)
    assert cp.returncode != 0, "validator should fail when last_build schema is pre-2.1.1 or missing zip parity"
    data = json.loads(cp.stdout)
    assert data.get("last_build_schema_ok") is False or data.get("zip_hash_match") is False

