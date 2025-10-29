"""Contracts and constants for the deterministic 20-pack build.

All values are pure data used across writers and validators.
"""

from __future__ import annotations

from typing import Final, List, Dict


CANONICAL_PACK_FILENAMES: Final[List[str]] = [
    "01_README+Directory-Map_v2.json",
    "02_Global-Instructions_v2.json",
    "03_Operating-Rules_v2.json",
    "04_Governance+Risk-Register_v2.json",
    "05_Safety+Privacy_Guardrails_v2.json",
    "06_Role-Recipes_Index_v2.json",
    "07_Subagent_Role-Recipes_v2.json",
    "08_Memory-Schema_v2.json",
    "09_Agent-Manifests_Catalog_v2.json",
    "10_Prompt-Pack_v2.json",
    "11_Workflow-Pack_v2.json",
    "12_Tool+Data-Registry_v2.json",
    "13_Knowledge-Graph+RAG_Config_v2.json",
    "14_KPI+Evaluation-Framework_v2.json",
    "15_Observability+Telemetry_Spec_v2.json",
    "16_Reasoning-Footprints_Schema_v1.json",
    "17_Lifecycle-Pack_v2.json",
    "18_Reporting-Pack_v2.json",
    "19_Overlay-Pack_SME-Domain_v1.json",
    "20_Overlay-Pack_Enterprise_v1.json",
]


KPI_TARGETS: Final[dict] = {
    "PRI_min": 0.95,
    "HAL_max": 0.02,
    "AUD_min": 0.90,
}


REQUIRED_EVENTS: Final[List[str]] = [
    "intake_loaded",
    "naics_confirmed",
    "profile_generated",
    "repo_generated",
    "gate_evaluation",
]


REQUIRED_ALERTS: Final[List[str]] = [
    "HAL_breach",
    "PRI_drop",
]


REQUIRED_HUMAN_GATE_ACTIONS: Final[List[str]] = [
    "legal_advice",
    "regulatory_interpretation",
]


PACK_ID_TO_FILENAME: Final[Dict[int, str]] = {i + 1: n for i, n in enumerate(CANONICAL_PACK_FILENAMES)}
FILENAME_TO_ID: Final[Dict[str, int]] = {n: i for i, n in PACK_ID_TO_FILENAME.items()}
