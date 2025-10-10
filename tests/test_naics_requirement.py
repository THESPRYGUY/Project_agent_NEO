"""Tests for NAICS requirement and enrichment in domain selector (Step 3)."""
from __future__ import annotations

import json
from pathlib import Path

from neo_agent.intake_app import create_app


def _build_payload(top_level: str, subdomain: str, tags=None, naics: dict | None = None):
    payload = {
        "agent_name": ["Selector Agent"],
        "agent_version": ["1.0.0"],
        "agent_persona": ["ENTJ"],
        "domain": ["Finance"],
        "role": ["Enterprise Analyst"],
        "toolsets": ["Data Analysis"],
        "attributes": ["Strategic"],
        "autonomy": ["60"],
        "confidence": ["55"],
        "collaboration": ["45"],
        "communication_style": ["Formal"],
        "collaboration_mode": ["Solo"],
        "notes": ["Domain selector NAICS tests"],
    }
    selector = {
        "topLevel": top_level,
        "subdomain": subdomain,
        "tags": tags or ["test"],
    }
    if naics is not None:
        selector["naics"] = naics
    payload["domain_selector"] = [json.dumps(selector)]
    return payload


def test_naics_required_for_sector_domains(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)
    payload = _build_payload("Sector Domains", "Energy & Infrastructure", tags=["infra"], naics=None)
    profile = app._build_profile(payload, {})
    # domain_selector should be omitted due to missing NAICS
    assert "domain_selector" not in profile["agent"]
    errs = profile.get("_validation", {}).get("domain_selector_errors", [])
    assert any("NAICS required" in e for e in errs)


def test_naics_rejected_invalid_code(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)
    payload = _build_payload(
        "Sector Domains",
        "Energy & Infrastructure",
        naics={"code": "999999"},
    )
    profile = app._build_profile(payload, {})
    assert "domain_selector" not in profile["agent"]
    errs = profile.get("_validation", {}).get("domain_selector_errors", [])
    assert any("Invalid NAICS code 999999" in e for e in errs)


def test_naics_enriches_reference_fields(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)
    # Provide minimal NAICS code; enrichment should fill details.
    # Provide only the code (no extra fields) so enrichment can safely populate reference
    # values. Supplying mismatching extra fields is treated as tampering and rejected.
    payload = _build_payload(
        "Sector Domains",
        "Energy & Infrastructure",
        naics={"code": "541611"},
    )
    profile = app._build_profile(payload, {})
    selector = profile["agent"].get("domain_selector")
    errs = profile.get("_validation", {}).get("domain_selector_errors", [])
    assert selector is not None, errs
    naics = selector.get("naics")
    assert naics and naics["code"] == "541611"
    assert naics["title"].startswith("Administrative Management")  # original reference title
    assert naics["level"] == 6
    path = naics["path"]
    assert path[0] == "54"
    assert path[-1] == "541611"
    assert "5416" in path


def test_subdomain_invalid_rejected(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)
    payload = _build_payload("Strategic Functions", "Not A Real Subdomain")
    profile = app._build_profile(payload, {})
    assert "domain_selector" not in profile["agent"]
    errs = profile.get("_validation", {}).get("domain_selector_errors", [])
    assert any("Invalid subdomain" in e for e in errs)
