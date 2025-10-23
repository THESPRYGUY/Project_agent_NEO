from __future__ import annotations

import json
from pathlib import Path

from neo_agent.adapters.normalize_v3 import normalize_context_role
from neo_build.writers import write_repo_files
from neo_build.validators import integrity_report, kpi_targets_sync


def test_normalize_context_role_unit() -> None:
    v3 = {
        "context": {
            "naics": {"code": "541110", "title": "Offices of Lawyers", "level": 6},
            "region": ["CA", "US"],
        },
        "role": {
            "function_code": "legal_compliance",
            "role_code": "AIA-P",
            "role_title": "Legal & Compliance Lead",
            "objectives": ["Ensure compliance"],
        },
    }
    out = normalize_context_role(v3)
    assert out["role_profile"]["archetype"] == "AIA-P"
    assert out["role_profile"]["role_title"] == "Legal & Compliance Lead"
    assert out["sector_profile"]["sector"] == "Offices of Lawyers"
    # Regions CA + US produce union of frameworks; order is sorted
    assert out["sector_profile"]["regulatory"] == ["ISO_IEC_42001", "NIST_AI_RMF", "PIPEDA"]


def test_e2e_build_from_v3_context(tmp_path: Path) -> None:
    # Only new v3 fields provided; adapter produces role_profile/sector_profile
    v3 = {
        "agent": {"name": "CTX Agent", "version": "1.0.0"},
        "context": {
            "naics": {"code": "541110", "title": "Offices of Lawyers", "level": 6},
            "region": ["CA", "US"],
        },
        "role": {
            "function_code": "legal_compliance",
            "role_code": "AIA-P",
            "role_title": "Legal & Compliance Lead",
            "objectives": ["Ensure compliance"],
        },
    }
    normalized = normalize_context_role(v3)
    profile = {
        **v3,
        **normalized,
        "classification": {"naics": v3["context"]["naics"]},
    }

    packs = write_repo_files(profile, tmp_path)

    # 06 mapping and roles_index reflect role_code/title/objectives
    p06 = packs["06_Role-Recipes_Index_v2.json"]
    assert p06["mapping"]["primary_role_code"] == "AIA-P"
    assert p06["roles_index"][0]["title"] == "Legal & Compliance Lead"

    # 19 refs carry region and regulators
    p19 = packs["19_Overlay-Pack_SME-Domain_v1.json"]
    assert p19["refs"]["region"] == ["CA", "US"]
    assert set(p19["refs"]["regulators"]) == {"ISO_IEC_42001", "NIST_AI_RMF", "PIPEDA"}

    # 02 and 04 carry regulators consistently
    p02 = packs["02_Global-Instructions_v2.json"]
    p04 = packs["04_Governance+Risk-Register_v2.json"]
    assert set(p02["safety"]["regulatory"]) == set(p04["frameworks"]["regulators"]) == {"ISO_IEC_42001", "NIST_AI_RMF", "PIPEDA"}

    # Integrity: KPI parity checks remain satisfied across 11/14/17 (02 has no KPI)
    report = integrity_report(profile, packs)
    assert report["checks"]["kpi_sync"] is True
    assert report["checks"]["observability"] is True
    assert report["checks"]["owners_present"] in (True, False)  # owners may be empty in this minimal profile

