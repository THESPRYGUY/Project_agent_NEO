from __future__ import annotations

from neo_agent.intake_app import IntakeApplication, _derive_objectives
from neo_build.validators import integrity_report
from neo_build.writers import write_repo_files


def test_derive_objectives_deterministic() -> None:
    mission = "Help teams secure data and ship compliant releases."
    use_cases = ["Map controls to audits", "Guide engineers on remediation"]
    first = _derive_objectives(mission, use_cases)
    second = _derive_objectives(mission, use_cases)

    assert 3 <= len(first) <= 5
    assert first == second
    assert all(first)


def test_objectives_explicit_from_params(tmp_path) -> None:
    app = IntakeApplication(base_dir=tmp_path)
    params = {
        "agent_name": ["Objectives Agent"],
        "agent_version": ["1.0.0"],
        "business_function": ["Operations"],
        "role_code": ["OPS:DIR"],
        "role_title": ["Ops Director"],
        "identity.agent_id": ["AGT-OBJ-001"],
        "objectives_raw": [" Ship reliably \nReduce incidents  "],
    }

    profile, errors, _ = app._canonical_profile_from_params(params)
    assert errors == {}
    expected = ["Ship reliably", "Reduce incidents"]
    assert profile["role_profile"]["objectives"] == expected
    assert profile["role_profile"]["objectives_status"] == "explicit"
    assert profile["role"]["objectives"] == expected


def test_objectives_derived_and_propagated(tmp_path) -> None:
    app = IntakeApplication(base_dir=tmp_path)
    params = {
        "agent_name": ["Derived Agent"],
        "agent_version": ["1.0.0"],
        "naics_code": ["541110"],
        "naics_title": ["Offices of Lawyers"],
        "naics_level": ["6"],
        "naics_lineage_json": ["[]"],
        "business_function": ["Legal & Compliance"],
        "role_code": ["AIA-P"],
        "role_title": ["Legal Lead"],
        "identity.agent_id": ["AGT-OBJ-002"],
        "notes": [
            '{"engagement_notes":{"mission":{"primary":"Guide teams on legal readiness","secondary":["Coach reviews","Flag risks early"]}}}'
        ],
    }

    profile, errors, _ = app._canonical_profile_from_params(params)
    assert errors == {}
    objectives = profile["role_profile"]["objectives"]
    assert objectives and profile["role_profile"]["objectives_status"] == "derived"
    assert profile["role"]["objectives"] == objectives

    packs = write_repo_files(profile, tmp_path / "packs")
    p06 = packs["06_Role-Recipes_Index_v2.json"]
    p09 = packs["09_Agent-Manifests_Catalog_v2.json"]
    assert p06["objectives"] == objectives
    assert p06["roles_index"][0]["objectives"] == objectives
    assert p09["agents"][0]["objectives"] == objectives


def test_integrity_report_marks_missing_objectives() -> None:
    profile = {"role_profile": {}}
    report = integrity_report(profile, {})
    objectives = report.get("objectives", {})
    assert objectives.get("status") == "missing"
    assert objectives.get("count") == 0
    assert any(
        "No objectives set" in msg for msg in objectives.get("warnings", [])
    ), "Missing objectives warning should be present"


def test_integrity_report_flags_generic_objectives() -> None:
    profile = {
        "role_profile": {
            "objectives": ["help user", "answer questions"],
            "objectives_status": "derived",
        }
    }
    report = integrity_report(profile, {})
    objectives = report.get("objectives", {})
    assert objectives.get("status") == "derived"
    assert objectives.get("count") == 2
    assert objectives.get("has_generic") is True
    assert any(
        "generic" in msg.lower() for msg in objectives.get("warnings", [])
    ), "Generic objectives warning expected"


def test_integrity_report_handles_explicit_objectives_without_warnings() -> None:
    profile = {
        "role_profile": {
            "objectives": ["Reduce incidents", "Triage risks"],
            "objectives_status": "explicit",
        }
    }
    report = integrity_report(profile, {})
    objectives = report.get("objectives", {})
    assert objectives.get("status") == "explicit"
    assert objectives.get("count") == 2
    assert objectives.get("has_generic") is False
    assert objectives.get("warnings") == []
