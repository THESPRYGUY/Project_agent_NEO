"""Schema validation tests for agent_profile schema (Step 5).

Uses the real project root so NAICS reference file is available.
Skips gracefully if jsonschema lib not installed (though dev extra installs it).
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from neo_agent.intake_app import create_app

jsonschema = pytest.importorskip("jsonschema")  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "agent_profile.schema.json"

with SCHEMA_PATH.open("r", encoding="utf-8") as f:
    SCHEMA = json.load(f)

Validator = jsonschema.Draft202012Validator if hasattr(jsonschema, "Draft202012Validator") else jsonschema.Draft7Validator  # type: ignore


def _validate(obj):
    v = Validator(SCHEMA)
    return sorted(v.iter_errors(obj), key=lambda e: list(e.path))


def _base_payload():
    return {
        "agent_name": ["Schema Agent"],
        "agent_version": ["1.0.0"],
        "agent_persona": ["ENTJ"],
        "domain": ["Finance"],
        "role": ["Enterprise Analyst"],
        "toolsets": ["Data Analysis"],
        "attributes": ["Strategic"],
        "autonomy": ["50"],
        "confidence": ["50"],
        "collaboration": ["50"],
        "communication_style": ["Formal"],
        "collaboration_mode": ["Solo"],
        "notes": ["Schema test"],
    }


def test_valid_profile_passes_schema():
    app = create_app(base_dir=PROJECT_ROOT)
    payload = _base_payload()
    from json import dumps
    payload["domain_selector"] = [dumps({
        "topLevel": "Strategic Functions",
        "subdomain": "Workflow Orchestration",
        "tags": ["workflow-orchestration"]
    })]
    profile = app._build_profile(payload, {})
    errors = _validate(profile)
    assert not errors, [e.message for e in errors]


def test_invalid_missing_naics_sector_omitted_domain_selector():
    app = create_app(base_dir=PROJECT_ROOT)
    payload = _base_payload()
    from json import dumps
    payload["domain_selector"] = [dumps({
        "topLevel": "Sector Domains",
        "subdomain": "Energy & Infrastructure",
        "tags": []
    })]
    profile = app._build_profile(payload, {})
    assert "domain_selector" not in profile["agent"], "Invalid sector domain selector should be omitted"


def test_invalid_naics_structure_omits_enrichment():
    app = create_app(base_dir=PROJECT_ROOT)
    payload = _base_payload()
    from json import dumps
    payload["domain_selector"] = [dumps({
        "topLevel": "Sector Domains",
        "subdomain": "Energy & Infrastructure",
        "tags": ["infra"],
        "naics": {"code": "541611", "title": "Tampered", "path": ["54"], "version": "2022"}  # malformed (missing level, path too short)
    })]
    profile = app._build_profile(payload, {})
    assert "domain_selector" not in profile["agent"], "Malformed NAICS payload should cause drop"


def test_valid_naics_enriched_passes():
    app = create_app(base_dir=PROJECT_ROOT)
    payload = _base_payload()
    from json import dumps
    payload["domain_selector"] = [dumps({
        "topLevel": "Sector Domains",
        "subdomain": "Energy & Infrastructure",
        "tags": ["infra"],
        "naics": {"code": "541611"}
    })]
    profile = app._build_profile(payload, {})
    ds = profile["agent"].get("domain_selector")
    assert ds and ds["naics"]["code"] == "541611"
    errors = _validate(profile)
    assert not errors, [e.message for e in errors]
