from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neo_build.writers import write_repo_files


@pytest.fixture()
def outdir(tmp_path: Path) -> Path:
    d = tmp_path / "repo"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_json(p: Path) -> Mapping[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def test_rbac_owners_propagation(outdir: Path) -> None:
    # Case 1: owners present -> roles = [CAIO,CPA,TeamLead] + sorted_unique(owners)
    profile_with_owners = {
        "identity": {"owners": ["OwnerA", "OwnerB"], "agent_id": "atlas"},
        "capabilities_tools": {"human_gate": {"actions": ["legal_advice"]}},
        # defaults that should be left alone if owners missing
        "governance": {"rbac": {"roles": ["ExistingRole"]}},
    }
    packs = write_repo_files(profile_with_owners, outdir)
    rules = _read_json(outdir / "03_Operating-Rules_v2.json")
    roles = rules.get("rbac", {}).get("roles", [])
    assert roles == ["CAIO", "CPA", "TeamLead", "OwnerA", "OwnerB"]

    # Case 2: owners missing/empty -> leave defaults unchanged
    outdir2 = outdir.parent / "repo2"
    outdir2.mkdir(parents=True, exist_ok=True)
    profile_no_owners = {
        "identity": {"agent_id": "atlas"},
        "capabilities_tools": {"human_gate": {"actions": ["legal_advice"]}},
        "governance": {"rbac": {"roles": ["ExistingRole"]}},
    }
    write_repo_files(profile_no_owners, outdir2)
    rules2 = _read_json(outdir2 / "03_Operating-Rules_v2.json")
    roles2 = rules2.get("rbac", {}).get("roles", [])
    assert roles2 == ["ExistingRole"]


def test_manifest_role_title(outdir: Path) -> None:
    profile = {
        "identity": {"agent_id": "atlas", "display_name": "Atlas"},
        # Precedence: role.role_title wins
        "role_profile": {"role_title": "Role From RoleProfile"},
        "role": {"role_title": "Selected Role Title"},
    }
    write_repo_files(profile, outdir)

    # 06 selected role title
    rri = _read_json(outdir / "06_Role-Recipes_Index_v2.json")
    selected_title = rri.get("roles_index", [{}])[0].get("title")
    # 06 title remains based on legacy precedence (role.title or role_profile.role_title)
    # may not equal final selected precedence; check 09 for final echo

    # 09 should mirror selected role_title
    amc = _read_json(outdir / "09_Agent-Manifests_Catalog_v2.json")
    agents = amc.get("agents", [])
    assert (
        isinstance(agents, list) and agents
    ), "agents list should have at least one entry"
    assert agents[0].get("role_title") == "Selected Role Title"


def test_manifest_role_title_fallbacks(outdir: Path) -> None:
    # Case A: role empty -> use role_profile.role_title
    profile_a = {
        "identity": {"agent_id": "atlas", "display_name": "Atlas"},
        "role_profile": {"role_title": "From RoleProfile"},
        "role": {},
    }
    write_repo_files(profile_a, outdir)
    amc_a = _read_json(outdir / "09_Agent-Manifests_Catalog_v2.json")
    assert amc_a.get("agents", [{}])[0].get("role_title") == "From RoleProfile"

    # Case B: role + role_profile empty -> fallback to 06.roles_index[*].title (which uses role.title legacy)
    outdir_b = outdir.parent / "repo_b"
    outdir_b.mkdir(parents=True, exist_ok=True)
    profile_b = {
        "identity": {"agent_id": "atlas", "display_name": "Atlas"},
        "role_profile": {},
        "role": {"title": "Legacy Role Title"},
    }
    write_repo_files(profile_b, outdir_b)
    amc_b = _read_json(outdir_b / "09_Agent-Manifests_Catalog_v2.json")
    assert amc_b.get("agents", [{}])[0].get("role_title") == "Legacy Role Title"
