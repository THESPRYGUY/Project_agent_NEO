#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
import difflib


REF_SSOT = Path("ref/intake/agent_profile.json")
GEN_DIR = Path("_generated")
DIFF_DIR = Path("_diffs")

FORBIDDEN_PATTERNS = [
    re.compile(r"\bAML\b", re.IGNORECASE),
    re.compile(r"\bFINANCIAL[\s_-]*CRIME\b", re.IGNORECASE),
    re.compile(r"\bN[-_\s]*BELL\b", re.IGNORECASE),
    re.compile(r"\bNIGEL\b", re.IGNORECASE),
    re.compile(r"\bNEO[-_\s]*AML\b", re.IGNORECASE),
]


def deep_sort(obj):
    if isinstance(obj, dict):
        return {k: deep_sort(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [deep_sort(x) for x in obj]
    return obj


def write_json(path: Path, data, sort_keys=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=sort_keys)
        f.write("\n")


def unified_diff(a_text: str, b_text: str, a_label: str, b_label: str) -> str:
    a_lines = a_text.splitlines(keepends=True)
    b_lines = b_text.splitlines(keepends=True)
    return "".join(difflib.unified_diff(a_lines, b_lines, fromfile=a_label, tofile=b_label))


def any_forbidden(text: str) -> str | None:
    for pat in FORBIDDEN_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(0)
    return None


def correct_ssot(ssot: dict) -> dict:
    # Ensure nested structures
    ssot.setdefault("agent", {})
    ssot.setdefault("role", {})
    ssot.setdefault("persona", {})
    ssot.setdefault("identity", {})
    ssot.setdefault("naics", {})
    ssot.setdefault("memory", {})

    # Turkey R&D alignment
    ssot["naics"]["code"] = "112330"  # Turkey Production

    canonical_id = "AGT-112330-TURKEY-RND-0001"
    agent_id = (ssot.get("agent") or {}).get("agent_id") or ""
    raw_dump = json.dumps(ssot, ensure_ascii=False)
    has_bad_id = agent_id.startswith("AGT-000000") or any_forbidden(agent_id or "")
    if not agent_id or has_bad_id:
        ssot["agent"]["agent_id"] = canonical_id
    else:
        # If an id exists but contains forbidden text, override
        if any_forbidden(agent_id or ""):
            ssot["agent"]["agent_id"] = canonical_id

    # Slug + display name cleanup (avoid AML references)
    ssot["agent"]["slug"] = "turkey-rnd"
    disp = (ssot["agent"].get("display_name") or ssot.get("role", {}).get("title") or "Turkey R&D Agent").strip()
    if any_forbidden(disp or ""):
        disp = "Turkey R&D Agent"
    ssot["agent"]["display_name"] = disp

    # Scope text (place in top-level 'scope' and under role.description if present)
    scope_text = "Turkey production R&D: food safety, processing, welfare & performance."
    ssot["scope"] = scope_text
    if isinstance(ssot.get("role"), dict):
        if not ssot["role"].get("description") or any_forbidden(str(ssot["role"].get("description", ""))):
            ssot["role"]["description"] = scope_text

    # Persona/owners
    ssot.setdefault("persona", {})
    ssot["persona"]["locked"] = True
    agent_p = ssot["persona"].get("agent") or {}
    agent_p["code"] = "ENTJ"
    ssot["persona"]["agent"] = agent_p
    if not ssot["identity"].get("owners"):
        ssot["identity"]["owners"] = ["CAIO", "CPA", "TeamLead"]

    # governance_eval
    ssot["governance_eval"] = {
        "classification_default": "confidential",
        "no_impersonation": True,
        "risk_register_tags": ssot.get("governance_eval", {}).get("risk_register_tags", []),
        "gates": {"PRI_min": 0.95, "hallucination_max": 0.02, "audit_min": 0.90},
    }

    # observability
    ssot["observability"] = {
        "channels": [
            {
                "id": "agentops://turkey-rnd-001",
                "events": ["workflow.start", "workflow.end", "guardrail.refusal", "error"],
                "pii_scrub": True,
            }
        ],
        "retention_days": 180,
    }

    # memory packs
    mem = ssot.get("memory") or {}
    mem["initial_memory_packs"] = [
        {"id": "poultry_microbio_glossary_v1", "scope": "semantic"},
        {"id": "cfia_usda_food_safety_refs_v1", "scope": "semantic"},
        {"id": "turkey_process_SOPs_v1", "scope": "procedural"},
    ]
    ssot["memory"] = mem

    # packaging paths
    ssot["packaging"] = {
        "output_paths": {
            "prompts": "10_Prompt-Pack_v2.json",
            "workflows": "11_Workflow-Pack_v2.json",
            "governance": "04_Governance+Risk-Register_v2.json",
            "kpi": "14_KPI+Evaluation-Framework_v2.json",
            "observability": "15_Observability+Telemetry_Spec_v2.json",
        }
    }

    # provenance
    ssot["provenance"] = {"attribution_policy": "inspired-by", "no_impersonation": True}

    # determinism knobs
    ssot["determinism"] = {
        "fixed_timestamp": "1970-01-01T00:00:00Z",
        "stable_seed": 1337,
        "deep_sort_keys": True,
    }

    return ssot


def main() -> int:
    if not REF_SSOT.exists():
        print("BLOCKED: SSOT missing (ref/intake/agent_profile.json)")
        return 2

    raw = REF_SSOT.read_text(encoding="utf-8")
    # Pre-scan but do not hard stop; allow remediation
    ssot = json.loads(raw)
    ssot = correct_ssot(ssot)

    # Deterministic deep-sort and write atomically (ref + mirror)
    canonical = deep_sort(ssot)
    before = raw
    after = json.dumps(canonical, ensure_ascii=False, indent=2)
    write_json(REF_SSOT, canonical, sort_keys=True)
    GEN_DIR.mkdir(parents=True, exist_ok=True)
    write_json(GEN_DIR / "agent_profile.json", canonical, sort_keys=True)
    DIFF_DIR.mkdir(parents=True, exist_ok=True)
    (DIFF_DIR / "agent_profile.diff").write_text(
        unified_diff(before, after, str(REF_SSOT), str(GEN_DIR / "agent_profile.json")), encoding="utf-8"
    )

    # Assertions
    dump_txt = json.dumps(canonical, ensure_ascii=False)
    bad = any_forbidden(dump_txt)
    if bad:
        print(f"BLOCKED: SSOT CONTAINS AML ARTIFACTS {bad}")
        return 3

    try:
        assert canonical.get("naics", {}).get("code") == "112330"
        assert canonical.get("agent", {}).get("agent_id") == "AGT-112330-TURKEY-RND-0001"
        assert canonical.get("persona", {}).get("locked") is True
        assert len(canonical.get("identity", {}).get("owners") or []) >= 1
        gates = canonical.get("governance_eval", {}).get("gates") or {}
        assert set(["PRI_min", "hallucination_max", "audit_min"]).issubset(gates.keys())
        obs = canonical.get("observability", {})
        ch0 = (obs.get("channels") or [{}])[0]
        assert ch0.get("id"), "observability.channels[0].id missing"
        assert int(obs.get("retention_days") or 0) >= 180
        assert len(canonical.get("memory", {}).get("initial_memory_packs") or []) >= 1
        outp = canonical.get("packaging", {}).get("output_paths") or {}
        for k in ["prompts", "workflows", "governance", "kpi", "observability"]:
            assert outp.get(k), f"packaging.output_paths.{k} missing"
        assert canonical.get("provenance", {}).get("no_impersonation") is True
        det = canonical.get("determinism", {})
        assert {"fixed_timestamp", "stable_seed", "deep_sort_keys"}.issubset(det.keys())
    except AssertionError as e:
        print(f"BLOCKED: SSOT {e}")
        return 3

    # Emit summary
    print(json.dumps({
        "agent_id": canonical["agent"]["agent_id"],
        "naics": canonical["naics"]["code"],
        "persona": canonical["persona"].get("agent", {}).get("code", ""),
        "owners_count": len(canonical["identity"]["owners"]),
        "obs_channel": canonical["observability"]["channels"][0]["id"],
        "memory_packs_count": len(canonical["memory"]["initial_memory_packs"]),
        "status": "PHASE-0.1 SSOT CORRECTED",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

