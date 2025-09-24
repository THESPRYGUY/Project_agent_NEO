"""Test helpers to build canonical agent profiles for build tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


_BASE_PROFILE: Dict[str, Any] = {
    "persona": {
        "name": "Atlas Ops Agent",
        "mbti": "entj",
        "summary": "Enterprise orchestrator for grid strategy.",
    },
    "domain": {
        "topLevel": "Sector Domains",
        "subdomain": "Data Center Strategy",
        "tags": ["ercot", "ontario", "hyperscale"],
        "naics": {
            "code": "51821",
            "title": "Data processing, hosting, and related services",
            "level": 5,
            "version": "NAICS 2022 v1.0",
            "path": ["51", "518", "5182", "51821"],
        },
    },
    "industry": {
        "naics": {
            "code": "51821",
            "title": "Data processing, hosting, and related services",
            "level": 5,
            "version": "NAICS 2022 v1.0",
            "path": ["51", "518", "5182", "51821"],
        }
    },
    "toolsets": {
        "capabilities": [
            "reasoning_planning",
            "data_rag",
            "orchestration",
        ],
        "connectors": [
            {
                "name": "notion",
                "scopes": ["read:db/*", "write:tasks"],
            }
        ],
        "governance": {
            "storage": "kv",
            "redaction": ["mask_pii", "never_store_secrets"],
            "retention": "default_365",
            "data_residency": "auto",
        },
        "ops": {
            "env": "staging",
            "dry_run": True,
            "latency_slo_ms": 1200,
            "cost_budget_usd": 5.0,
        },
    },
    "traits": {
        "traits": {
            "detail_oriented": 70,
            "collaborative": 68,
            "proactive": 82,
            "strategic": 90,
            "empathetic": 55,
            "experimental": 60,
            "efficient": 75,
        },
        "provenance": "manual",
        "version": "1.0",
        "mbti": "entj",
    },
    "preferences": {
        "autonomy": 80,
        "confidence": 65,
        "collaboration": 70,
        "comm_style": "executive_brief",
        "collab_mode": "cross_functional",
        "prefs_knobs": {
            "confirmation_gate": "none",
            "rec_depth": "balanced",
            "handoff_freq": "medium",
            "communication": {
                "word_cap": 200,
                "bulletize_default": True,
                "include_call_to_action": True,
                "allow_extended_rationale": False,
                "include_code_snippets": False,
            },
            "collaboration": {
                "require_pair_confirmation": False,
                "require_review_handoff": False,
            },
        },
        "provenance": "manual",
        "version": "1.0",
    },
}


def make_profile(**updates: Any) -> Dict[str, Any]:
    profile = deepcopy(_BASE_PROFILE)
    for key, value in updates.items():
        profile[key] = value
    return profile


DEFAULT_OPTIONS: Dict[str, Any] = {
    "include_examples": False,
    "git_init": False,
    "zip": True,
    "overwrite": "safe",
}
