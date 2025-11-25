from __future__ import annotations

import json
from pathlib import Path

from neo_build import writers


SPEC_PATH = Path("canon/15_Observability+Telemetry_Spec_v2.json")
FIXTURE_PATH = Path("fixtures/strategy_invocation_hce_drac.json")
NULLABLE_FIELDS = {
    "token_count",
    "tokens_input",
    "tokens_output",
    "latency_ms",
    "pri_score",
    "hal_score",
    "aud_score",
}


def _load_strategy_entry() -> dict:
    data = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    entries = data.get("strategy_invocation") or []
    assert entries, "strategy_invocation spec block missing"
    return entries[0]


def _find_case(
    examples: list[dict], status: str, hitl_required: bool, hitl_applied: bool
) -> dict:
    for example in examples:
        if (
            example.get("status") == status
            and example.get("hitl_required") is hitl_required
            and example.get("hitl_applied") is hitl_applied
        ):
            return example
    raise AssertionError(
        f"Unable to find strategy_invocation example for {status} (hitl_required={hitl_required}, hitl_applied={hitl_applied})"
    )


def test_strategy_invocation_fixture_matches_schema() -> None:
    entry = _load_strategy_entry()
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    allowed_fields = set(entry.get("fields", []))
    required_fields = set(entry.get("required_fields", []))

    assert set(fixture.keys()).issubset(allowed_fields)
    for field in required_fields:
        assert field in fixture, f"{field} missing from strategy_invocation fixture"
        if field not in NULLABLE_FIELDS:
            assert fixture[field] not in (None, ""), f"{field} must be populated"

    assert fixture["kpi_targets"] == entry["kpi_targets"]
    safety_flags = fixture.get("safety_flags") or {}
    assert "kpi_targets" not in safety_flags
    assert fixture["hitl_required"] is True
    assert fixture["hitl_applied"] is False
    assert fixture["hitl_actor"] is None


def test_strategy_invocation_block_covers_hitl_semantics() -> None:
    block = writers._strategy_invocation_block(
        "AGT-TEST-001"
    )  # noqa: SLF001 - internal helper exercised via tests
    entry = block[0]
    examples = entry.get("examples", [])
    assert examples, "canonical strategy_invocation block missing examples"

    pending = _find_case(examples, "hitl_pending", True, False)
    completed_non_hitl = _find_case(examples, "completed", False, False)
    completed_hitl = _find_case(examples, "completed", True, True)

    assert pending["agent_id"] == "AGT-TEST-001"
    assert completed_non_hitl["hitl_actor"] is None
    assert isinstance(completed_hitl["hitl_actor"], str)

    for example in (pending, completed_non_hitl, completed_hitl):
        assert example["kpi_targets"] == entry["kpi_targets"]
        assert "kpi_targets" not in (example.get("safety_flags") or {})


def test_strategy_invocation_examples_have_correlation_fields() -> None:
    block = writers._strategy_invocation_block("AGT-CORR-TEST")
    example = block[0]["examples"][0]
    for field in (
        "run_id",
        "workflow_run_id",
        "correlation_id",
        "task_id",
        "footprint_id",
        "scenario_id",
    ):
        assert field in example and isinstance(example[field], str) and example[field]
    assert example["event_type"] == "strategy_invocation"


def test_strategy_invocation_fixture_correlation_fields_present() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    for field in ("run_id", "workflow_run_id", "correlation_id"):
        assert isinstance(fixture[field], str) and fixture[field]
