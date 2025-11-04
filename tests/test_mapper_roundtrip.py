from __future__ import annotations

import json
from pathlib import Path

import pytest

from mapper import apply_intake


def _write_pack(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@pytest.fixture()
def intake_payload() -> dict:
    return {
        "intake_version": "v1",
        "metadata": {
            "agent_id": "AGT-TEST-0001",
            "project_code": "AB007",
            "environment": "staging",
            "submitted_at": "2025-11-03T12:00:00Z",
            "owners": ["CAIO", "CPA"],
            "notes": "Roundtrip mapping test payload.",
        },
        "determinism": {
            "fixed_timestamp": True,
            "stable_seed": True,
            "deep_sort_keys": True,
            "timestamp_value": "1970-01-01T00:00:00Z",
            "seed_value": 1337,
        },
        "rbac": {
            "roles": ["CAIO", "CPA", "TeamLead"],
        },
        "memory": {
            "scopes": ["episodic:projects/*", "semantic:domain/*"],
            "retention": {"episodic": 180, "semantic": 365},
            "permissions": {
                "CAIO": {
                    "read": ["episodic:projects/*"],
                    "write": ["episodic:projects/*"],
                },
                "CPA": {
                    "read": ["semantic:domain/*"],
                    "write": [],
                },
            },
            "writeback_rules": [
                "Log writes with actor, checksum, and change_reason.",
                "Reject duplicate content without version bump.",
            ],
        },
        "connectors": [
            {
                "name": "sharepoint",
                "enabled": True,
                "scopes": ["read", "site.admin"],
                "secret_ref": "vault://connectors/sharepoint",
            },
            {
                "name": "vector-store",
                "enabled": False,
                "scopes": ["embedding_index"],
                "secret_ref": "vault://connectors/vector",
            },
        ],
        "data_sources": ["SRC-KB-001", "SRC-KB-010"],
        "governance": {
            "classification_default": "confidential",
            "pii_flags": ["basic_contact", "customer_record"],
            "risk_register_tags": ["safety", "compliance"],
        },
        "human_gate": {"actions": ["legal_advice", "regulatory_interpretation"]},
    }


@pytest.fixture()
def pack_root(tmp_path: Path) -> Path:
    pack_dir = tmp_path
    _write_pack(
        pack_dir / "03_Operating-Rules_v2.json",
        {
            "rbac": {"roles": ["Legacy"]},
        },
    )
    _write_pack(
        pack_dir / "04_Governance+Risk-Register_v2.json",
        {
            "risk_register_tags": [],
        },
    )
    _write_pack(
        pack_dir / "05_Safety+Privacy_Guardrails_v2.json",
        {
            "data_classification": {"default": "internal"},
        },
    )
    _write_pack(
        pack_dir / "08_Memory-Schema_v2.json",
        {
            "memory_scopes": [],
            "retention": {},
            "permissions": {"notes": "Existing notes", "roles": {}},
            "writeback_rules": ["Outdated rule"],
        },
    )
    _write_pack(pack_dir / "11_Workflow-Pack_v2.json", {})
    _write_pack(
        pack_dir / "12_Tool+Data-Registry_v2.json",
        {
            "connectors": [],
            "data_sources": [],
        },
    )
    return pack_dir


def test_apply_intake_dry_run_reports_changes(pack_root: Path, intake_payload: dict) -> None:
    result = apply_intake(intake_payload, pack_root, dry_run=True)
    expected_files = {
        "03_Operating-Rules_v2.json",
        "04_Governance+Risk-Register_v2.json",
        "05_Safety+Privacy_Guardrails_v2.json",
        "08_Memory-Schema_v2.json",
        "11_Workflow-Pack_v2.json",
        "12_Tool+Data-Registry_v2.json",
    }
    assert set(result["changed_files"]) == expected_files
    assert result["dry_run"] is True
    # diff report should enumerate each pack
    reported = {entry["pack_file"] for entry in result["diff_report"]}
    assert reported == expected_files


def test_apply_intake_writes_expected_updates(pack_root: Path, intake_payload: dict) -> None:
    apply_intake(intake_payload, pack_root, dry_run=False)

    pack03 = json.loads((pack_root / "03_Operating-Rules_v2.json").read_text(encoding="utf-8"))
    assert pack03["rbac"]["roles"] == ["CAIO", "CPA", "TeamLead"]

    pack04 = json.loads((pack_root / "04_Governance+Risk-Register_v2.json").read_text(encoding="utf-8"))
    assert pack04["risk_register_tags"] == ["safety", "compliance"]

    pack05 = json.loads((pack_root / "05_Safety+Privacy_Guardrails_v2.json").read_text(encoding="utf-8"))
    assert pack05["pii_flags"] == ["basic_contact", "customer_record"]
    assert pack05["data_classification"]["default"] == "confidential"

    pack08 = json.loads((pack_root / "08_Memory-Schema_v2.json").read_text(encoding="utf-8"))
    assert pack08["memory_scopes"] == ["episodic:projects/*", "semantic:domain/*"]
    assert pack08["retention"]["episodic"]["retention_days"] == 180
    assert pack08["retention"]["semantic"]["retention_days"] == 365
    assert pack08["permissions"]["roles"] == intake_payload["memory"]["permissions"]
    assert pack08["permissions"]["notes"] == "Existing notes"
    assert pack08["writeback_rules"] == intake_payload["memory"]["writeback_rules"]

    pack11 = json.loads((pack_root / "11_Workflow-Pack_v2.json").read_text(encoding="utf-8"))
    assert pack11["human_gate_actions"] == ["legal_advice", "regulatory_interpretation"]

    pack12 = json.loads((pack_root / "12_Tool+Data-Registry_v2.json").read_text(encoding="utf-8"))
    assert {connector["name"] for connector in pack12["connectors"]} == {"sharepoint", "vector-store"}
    sharepoint = next(c for c in pack12["connectors"] if c["name"] == "sharepoint")
    assert sharepoint["id"] == "sharepoint"
    assert sharepoint["secret_ref"] == "vault://connectors/sharepoint"
    assert sharepoint["scopes"] == ["read", "site.admin"]
    assert pack12["data_sources"] == ["SRC-KB-001", "SRC-KB-010"]
