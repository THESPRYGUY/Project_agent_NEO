from __future__ import annotations

from pathlib import Path

import pytest

from neo_build.scaffolder import enrich_single


pytestmark = pytest.mark.unit


def test_enrich_does_not_overwrite_existing_values() -> None:
    profile = {"identity": {"agent_id": "atlas"}}
    fname = "02_Global-Instructions_v2.json"
    payload = {
        "constraints": {"governance_file": "CUSTOM_GOV.json"},
        "agentic_policies": {"routing": {"workflow_pack": "CUSTOM_WORKFLOW.json"}},
        "observability": {
            "telemetry_spec": "CUSTOM_OBS.json",
            "kpi_targets": {"PRI_min": 0.95, "HAL_max": 0.02, "AUD_min": 0.9},
        },
    }
    out = enrich_single(profile, fname, payload)
    # Existing values remain
    assert out["constraints"]["governance_file"] == "CUSTOM_GOV.json"
    assert out["agentic_policies"]["routing"]["workflow_pack"] == "CUSTOM_WORKFLOW.json"
    assert out["observability"]["telemetry_spec"] == "CUSTOM_OBS.json"
    # Missing values are filled (e.g., prompt_pack, eval_framework_file)
    assert "prompt_pack" in out["agentic_policies"]["routing"]
    assert "eval_framework_file" in out["constraints"]
