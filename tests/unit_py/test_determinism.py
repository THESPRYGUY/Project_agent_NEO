from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def _hash_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def test_full_builds_byte_identical(tmp_path: Path, monkeypatch) -> None:
    # Force FULL contract mode and deterministic timestamp behavior
    monkeypatch.setenv("NEO_CONTRACT_MODE", "full")
    monkeypatch.setenv("CI", "1")

    from neo_build.contracts import CANONICAL_PACK_FILENAMES
    from neo_build.writers import write_repo_files

    repo1 = tmp_path / "r1"
    repo2 = tmp_path / "r2"
    repo1.mkdir(parents=True, exist_ok=True)
    repo2.mkdir(parents=True, exist_ok=True)

    # Minimal but complete profile
    profile = {
        "identity": {
            "agent_id": "determinism-agent",
            "display_name": "Deterministic Agent",
            "owners": ["CAIO", "CPA", "TeamLead"],
            "no_impersonation": True,
        },
        "agent": {"name": "DeterminismAgent", "version": "1.0.0"},
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

    write_repo_files(profile, repo1)
    write_repo_files(profile, repo2)

    # Compare hashes for all 20 canonical files
    for name in CANONICAL_PACK_FILENAMES:
        p1 = repo1 / name
        p2 = repo2 / name
        assert p1.exists() and p2.exists(), f"missing file: {name}"
        assert _hash_file(p1) == _hash_file(p2), f"hash mismatch for {name}"
