from __future__ import annotations

from adapters.legacy_to_v3 import upgrade


def test_upgrade_minimal_legacy() -> None:
    legacy = {
        "agent": {"name": "Atlas Analyst", "version": "1.0.0", "persona": "ENTJ"},
        "identity": {
            "agent_id": "atlas",
            "display_name": "Atlas Analyst",
            "no_impersonation": True,
        },
        "role_profile": {
            "role_title": "Enterprise Analyst",
            "role_recipe_ref": "RR-001",
            "objectives": ["Dashboards"],
        },
        "sector_profile": {
            "sector": "Finance",
            "region": ["NA"],
            "regulatory": ["SEC"],
        },
        "capabilities_tools": {
            "tool_connectors": [
                {
                    "name": "clm",
                    "enabled": True,
                    "scopes": ["read"],
                    "secret_ref": "SET_ME",
                }
            ],
            "human_gate": {"actions": ["legal_advice"]},
        },
        "memory": {
            "memory_scopes": ["customer"],
            "initial_memory_packs": ["m1"],
            "optional_packs": [],
            "data_sources": ["kb_main"],
        },
        "governance_eval": {
            "risk_register_tags": ["gdpr"],
            "pii_flags": ["email"],
            "classification_default": "confidential",
        },
        "classification": {"naics": {"code": "541"}},
    }

    v3 = upgrade(legacy)
    assert v3["meta"]["version"] == "v3-intake"
    assert v3["agent_profile"]["name"] == "Atlas Analyst"
    assert v3["identity"]["agent_id"] == "atlas"
    assert v3["role"]["recipe_ref"] == "RR-001"
    assert v3["domain"]["naics"]["code"] == "541"
    assert v3["tools"]["connectors"][0]["name"] == "clm"
    assert v3["memory"]["packs"]["initial"] == ["m1"]
    assert v3["privacy"]["classification_default"] == "confidential"
