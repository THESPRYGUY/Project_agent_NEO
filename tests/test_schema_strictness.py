from __future__ import annotations

import copy

import pytest

from mapper import IntakeValidationError, validate_intake


def _base_payload() -> dict:
    return {
        "intake_version": "v1",
        "metadata": {
            "agent_id": "AGT-VALID-001",
            "project_code": "AB007",
            "environment": "prod",
            "submitted_at": "2025-11-03T08:00:00Z",
            "owners": ["CAIO"],
            "notes": "Schema validation happy path.",
        },
        "determinism": {
            "fixed_timestamp": True,
            "stable_seed": True,
            "deep_sort_keys": True,
            "timestamp_value": "1970-01-01T00:00:00Z",
            "seed_value": 2025,
        },
        "rbac": {"roles": ["CAIO"]},
        "memory": {
            "scopes": ["semantic:domain/*"],
            "retention": {"semantic": 365},
            "permissions": {
                "CAIO": {
                    "read": ["semantic:domain/*"],
                    "write": ["semantic:domain/*"],
                }
            },
            "writeback_rules": ["Ensure semantic updates are logged."],
        },
        "connectors": [
            {
                "name": "knowledge-base",
                "enabled": True,
                "scopes": ["read"],
                "secret_ref": "vault://kb/primary",
            }
        ],
        "data_sources": ["SRC-KB-PRIMARY"],
        "governance": {
            "classification_default": "confidential",
            "pii_flags": ["basic_contact"],
            "risk_register_tags": [],
        },
        "human_gate": {"actions": ["legal_advice"]},
    }


def test_validate_intake_passes_for_valid_payload() -> None:
    payload = _base_payload()
    validate_intake(payload)


def test_validate_intake_blocks_unknown_top_level_key() -> None:
    payload = _base_payload()
    payload["unexpected"] = "value"
    with pytest.raises(IntakeValidationError):
        validate_intake(payload)


def test_validate_intake_enforces_enums() -> None:
    payload = _base_payload()
    invalid = copy.deepcopy(payload)
    invalid["governance"]["classification_default"] = "top_secret"
    with pytest.raises(IntakeValidationError):
        validate_intake(invalid)
