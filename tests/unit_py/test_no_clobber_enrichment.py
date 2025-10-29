from pathlib import Path
from typing import Mapping

from neo_build.scaffolder import enrich_single


def _profile_min() -> Mapping[str, object]:
    return {
        "identity": {"agent_id": "atlas", "owners": ["CAIO", "CPA", "TeamLead"]},
        "persona": {"persona_label": "ENTJ", "tone": "crisp, analytical, executive", "formality": "high"},
        "governance_eval": {"classification_default": "confidential"},
    }


def test_no_clobber_prompt_pack_modules() -> None:
    profile = _profile_min()
    payload = {
        "modules": [{"id": "custom.mod", "name": "Custom"}],
        "reasoning_patterns": ["Custom Pattern"],
        "guardrails": {"no_impersonation": False},
        "output_contracts": {"memo": {"sections": ["X"]}},
    }
    out = enrich_single(profile, "10_Prompt-Pack_v2.json", payload)
    # Ensure original modules preserved and not overwritten
    mods = [m.get("id") for m in out.get("modules", [])]
    assert "custom.mod" in mods
    # Guardrails do not flip existing flags
    assert out.get("guardrails", {}).get("no_impersonation") is False


def test_no_clobber_workflow_pack_gates_and_graphs() -> None:
    profile = _profile_min()
    payload = {
        "gates": {"kpi_targets": {"PRI_min": 0.99, "HAL_max": 0.01, "AUD_min": 0.91}},
        "graphs": [{"name": "UserFlow", "nodes": [{"id": "a", "module_id": "custom.mod"}]}],
    }
    out = enrich_single(profile, "11_Workflow-Pack_v2.json", payload)
    # Ensure provided KPI targets not clobbered
    kpi = (out.get("gates") or {}).get("kpi_targets")
    assert kpi == {"PRI_min": 0.99, "HAL_max": 0.01, "AUD_min": 0.91}
    # Graphs name preserved
    assert out.get("graphs", [])[0].get("name") == "UserFlow"


def test_no_clobber_reporting_templates() -> None:
    profile = _profile_min()
    payload = {
        "templates": [{"id": "user", "name": "User Template", "fields": ["step_id"]}],
        "outputs": ["pdf"],
        "publishing": {"channels": ["email_internal"]},
    }
    out = enrich_single(profile, "18_Reporting-Pack_v2.json", payload)
    # Provided template remains first and intact
    assert out.get("templates", [])[0].get("id") == "user"
    assert out.get("outputs") == ["pdf"]
