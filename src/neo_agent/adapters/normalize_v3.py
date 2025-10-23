"""Normalization adapter for context + role (v3 → builder-compatible keys).

This small adapter translates a v3-style payload into the fields expected by
the existing builder (role_profile, sector_profile). It purposefully avoids
changing builder contracts and keeps logic deterministic.

Input example (v3):

    {
      "context": {
        "naics": {"code": "541110", "title": "Offices of Lawyers", ...},
        "region": ["CA", "US"]
      },
      "role": {
        "function_code": "legal_compliance",
        "role_code": "AIA-P",
        "role_title": "Legal & Compliance Lead",
        "objectives": ["Ensure compliance"]
      }
    }

Output (merged into intake):

    {
      "role_profile": {
        "archetype": "AIA-P",
        "role_title": "Legal & Compliance Lead",
        "objectives": ["Ensure compliance"]
      },
      "sector_profile": {
        "sector": "Offices of Lawyers",
        "region": ["CA", "US"],
        "regulatory": ["ISO_IEC_42001", "NIST_AI_RMF", "PIPEDA"]
      }
    }
"""

from __future__ import annotations

from typing import Any, Dict, Mapping


def _derive_sector_from_naics(naics: Mapping[str, Any] | None) -> str:
    if isinstance(naics, Mapping):
        title = str(naics.get("title") or "").strip()
        if title:
            return title
    return "MULTI"


def _compute_regulators(regions: list[str] | None) -> list[str]:
    regs: set[str] = set()
    regions = list(regions or [])
    # Minimal, deterministic mapping
    if "CA" in regions:
        regs.update(["NIST_AI_RMF", "PIPEDA", "ISO_IEC_42001"])
    if "US" in regions:
        regs.update(["NIST_AI_RMF", "ISO_IEC_42001"])
    if "EU" in regions:
        regs.update(["EU_AI_Act", "GDPR", "ISO_IEC_42001"])
    return sorted(regs)


def normalize_context_role(v3: Mapping[str, Any]) -> Dict[str, Any]:
    ctx = v3.get("context") if isinstance(v3, Mapping) else None
    role = v3.get("role") if isinstance(v3, Mapping) else None
    ctx = ctx if isinstance(ctx, Mapping) else {}
    role = role if isinstance(role, Mapping) else {}

    region = ctx.get("region")
    if not isinstance(region, list):
        region = ["CA"]

    naics = ctx.get("naics") if isinstance(ctx.get("naics"), Mapping) else {}

    out: Dict[str, Any] = {
        "role_profile": {
            "archetype": str(role.get("role_code", "AIA-P")),
            "role_title": str(role.get("role_title", "")),
            "objectives": list(role.get("objectives", []) or []),
        },
        "sector_profile": {
            "sector": _derive_sector_from_naics(naics),
            "region": list(region),
            "regulatory": _compute_regulators(region),
        },
    }
    return out

