from __future__ import annotations

import json
from pathlib import Path


def jdump(obj) -> str:
    return json.dumps(obj, indent=2)


def write(p: Path, payload):
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        p.write_text(payload, encoding="utf-8")
    else:
        p.write_text(jdump(payload), encoding="utf-8")


def read(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def test_generated_autofix_p0_p1_p2(tmp_path: Path) -> None:
    root = tmp_path / "generated_repos"
    proj = root / "Demo"
    proj.mkdir(parents=True)

    # Minimal files with blanks
    write(proj / "06_Role-Recipes_Index_v2.json", {
        "archetype": "FIN:CONTROLLER",
        "mapping": {"primary_role_code": "FIN:CONTROLLER"},
        "role_recipe_ref": "",
        "roles_index": [{"code": "FIN:CONTROLLER", "title": "Corporate Controller", "objectives": []}],
        "version": 2,
    })
    write(proj / "07_Subagent_Role-Recipes_v2.json", {"recipes": []})
    write(proj / "09_Agent-Manifests_Catalog_v2.json", {"agents": [{"agent_id": "", "display_name": "Demo Agent"}]})
    write(proj / "11_Workflow-Pack_v2.json", {"defaults": {"persona": "ENTP", "tone": ""}})
    write(proj / "19_Overlay-Pack_SME-Domain_v1.json", {"industry": "", "naics": {"title": "Wholesale Trade"}, "region": []})
    write(proj / "04_Governance+Risk-Register_v2.json", {"owners": [], "risk_register": [{"mitigation": "TBD"}]})
    write(proj / "agent_profile.json", {"agent": {"mbti": {"mbti_code": "ESTJ", "suggested_traits": []}}})

    from scripts.generated_autofix import run

    # First run applies fixes
    results = run(root, write=True)
    assert results and results[0].p0_fixed >= 2

    # Validate changes
    d06 = read(proj / "06_Role-Recipes_Index_v2.json")
    assert d06.get("role_recipe_ref")
    d09 = read(proj / "09_Agent-Manifests_Catalog_v2.json")
    assert d09["agents"][0]["agent_id"]
    d11 = read(proj / "11_Workflow-Pack_v2.json")
    assert d11["defaults"]["tone"]
    d19 = read(proj / "19_Overlay-Pack_SME-Domain_v1.json")
    assert d19.get("industry") or not (proj / "19_Overlay-Pack_SME-Domain_v1.json").exists()
    d04 = read(proj / "04_Governance+Risk-Register_v2.json")
    assert d04["owners"] or d04["risk_register"][0]["mitigation"] != "TBD"
    ap = read(proj / "agent_profile.json")
    assert len(ap["agent"]["mbti"]["suggested_traits"]) >= 3

    # Second run idempotent
    results2 = run(root, write=True)
    # No additional P0 fixes should be necessary
    assert sum(r.p0_fixed for r in results2) == 0

