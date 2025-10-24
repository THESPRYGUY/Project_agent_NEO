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
    # Case 1: owners present -> roles = unique(owners ∪ [CAIO, CPA, TeamLead])
    profile_with_owners = {
        "identity": {"owners": ["OwnerA", "OwnerB"], "agent_id": "atlas"},
        "capabilities_tools": {"human_gate": {"actions": ["legal_advice"]}},
        # defaults that should be left alone if owners missing
        "governance": {"rbac": {"roles": ["ExistingRole"]}},
    }
    packs = write_repo_files(profile_with_owners, outdir)
    rules = _read_json(outdir / "03_Operating-Rules_v2.json")
    roles = set(rules.get("rbac", {}).get("roles", []))
    assert roles == {"OwnerA", "OwnerB", "CAIO", "CPA", "TeamLead"}

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
        # Both provided: prefer profile.role.title deterministically
        "role_profile": {"role_title": "Role From Profile"},
        "role": {"title": "Selected Role Title"},
    }
    write_repo_files(profile, outdir)

    # 06 selected role title
    rri = _read_json(outdir / "06_Role-Recipes_Index_v2.json")
    selected_title = rri.get("roles_index", [{}])[0].get("title")
    assert selected_title == "Selected Role Title"

    # 09 should mirror selected role_title
    amc = _read_json(outdir / "09_Agent-Manifests_Catalog_v2.json")
    agents = amc.get("agents", [])
    assert isinstance(agents, list) and agents, "agents list should have at least one entry"
    assert agents[0].get("role_title") == selected_title
