from __future__ import annotations

import pytest

from mapper import validate_intake, IntakeValidationError


def _invalid_payload() -> dict:
    return {
        "intake_version": "v1",
        "metadata": {
            "agent_id": "bad id",
            "project_code": "A",
            "environment": "prod",
            "submitted_at": "not-a-timestamp",
        },
        "determinism": {
            "fixed_timestamp": True,
            "stable_seed": True,
            "deep_sort_keys": True,
        },
        "rbac": {"roles": ["AdminTeam"]},
        "memory": {
            "scopes": ["semantic:domain/*"],
            "retention": {"episodic": 90},
            "permissions": {
                "AdminTeam": {
                    "read": [],
                    "write": [],
                }
            },
            "writeback_rules": ["All writes audited."],
        },
        "connectors": [],
        "data_sources": ["SRC-FOO-01"],
        "governance": {
            "classification_default": "public",
            "pii_flags": ["none"],
            "risk_register_tags": [],
        },
        "human_gate": {"actions": ["legal_advice"]},
    }


def test_multi_error_is_sorted_and_stable() -> None:
    payload = _invalid_payload()
    with pytest.raises(IntakeValidationError) as excinfo:
        validate_intake(payload)
    lines = [
        line.strip()
        for line in str(excinfo.value).splitlines()
        if line.strip() and not line.startswith("Intake contract validation failed")
    ]
    prefixes = [
        "connectors",
        "memory/permissions/AdminTeam/read",
        "metadata/agent_id",
        "metadata/project_code",
    ]
    assert len(lines) == 4
    observed = [line.split(":", 1)[0] for line in lines]
    assert observed == prefixes
