"""Profile compiler: produce a normalized, compiled view of the intake profile.

This module does not change the raw intake contract. It exposes a single
function, :func:`compile_profile`, which returns a dictionary that can be
embedded under ``_compiled`` in ``agent_profile.json`` and/or written as a
standalone file.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping
from datetime import datetime, timezone
import re


def _slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = value.replace("_", "-")
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^a-z0-9\-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def _coerce_map(obj: Any) -> dict:
    return dict(obj) if isinstance(obj, Mapping) else {}


def _persona_meta(profile: Mapping[str, Any]) -> Dict[str, Any] | None:
    # Mirrors logic in spec_generator._extract_persona_metadata but kept local to avoid import cycles.
    def coerce(candidate: Any) -> Dict[str, Any] | None:
        if not isinstance(candidate, Mapping):
            return None
        code = candidate.get("mbti_code") or candidate.get("code")
        if not code:
            return None
        axes_src = candidate.get("axes")
        axes = dict(axes_src) if isinstance(axes_src, Mapping) else {}
        traits_src = candidate.get("suggested_traits", [])
        traits = []
        if isinstance(traits_src, list):
            for item in traits_src:
                traits.append(item if isinstance(item, Mapping) else {"name": str(item)})
        return {
            "mbti_code": str(code).upper(),
            "name": str(candidate.get("name") or candidate.get("nickname") or ""),
            "description": str(candidate.get("description") or candidate.get("summary") or ""),
            "axes": axes,
            "suggested_traits": traits,
        }

    persona = _coerce_map(profile.get("persona"))
    if persona:
        meta = coerce(persona.get("persona_details"))
        if meta:
            return meta
        agent = _coerce_map(persona.get("agent"))
        if agent:
            meta = coerce(agent.get("mbti"))
            if meta:
                return meta
    agent = _coerce_map(profile.get("agent"))
    if agent:
        meta = coerce(_coerce_map(agent).get("mbti"))
        if meta:
            return meta
    fallback = profile.get("persona_details")
    return coerce(fallback)


def _normalized_list(values: Any) -> list[str]:
    out: list[str] = []
    if isinstance(values, list):
        items = values
    elif isinstance(values, str):
        items = [v.strip() for v in values.split(",") if v.strip()]
    else:
        items = []
    for item in items:
        if not item:
            continue
        slug = _slugify(str(item)).replace("-", "_")
        if slug and slug not in out:
            out.append(slug)
    return out


def compile_profile(profile: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a compiled, normalized view of the ``profile``.

    The returned structure is intentionally flat and typed to simplify
    templating across the agent repo.
    """

    agent = _coerce_map(profile.get("agent"))
    name = str(agent.get("name") or "").strip()
    version = str(agent.get("version") or "1.0.0").strip()
    persona = _persona_meta(profile)

    role = _coerce_map(profile.get("role"))
    business_function = str(profile.get("business_function") or role.get("function") or "").strip()

    naics = _coerce_map(profile.get("naics") or _coerce_map(profile.get("classification")).get("naics"))

    routing = _coerce_map(profile.get("routing_defaults") or profile.get("routing_hints"))

    toolsets = _coerce_map(profile.get("toolsets"))
    attributes = _coerce_map(profile.get("attributes"))
    preferences = _coerce_map(profile.get("preferences"))
    sliders = _coerce_map(preferences.get("sliders"))

    compiled: Dict[str, Any] = {
        "version": version or "1.0.0",
        "meta": {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "slugs": {
            "agent": _slugify("-".join([p for p in [name, version] if p])),
        },
        "agent": {
            "name": name,
            "version": version,
            "persona": persona or agent.get("persona") or "",
        },
        "business": {
            "function": business_function,
            "role": {
                "code": role.get("code", ""),
                "title": role.get("title", ""),
                "seniority": role.get("seniority", ""),
            },
        },
        "classification": {"naics": naics},
        "routing": {
            "workflows": routing.get("workflows", []),
            "connectors": routing.get("connectors", []),
            "report_templates": routing.get("report_templates", []),
            "autonomy_default": routing.get("autonomy_default"),
            "safety_bias": routing.get("safety_bias"),
            "kpi_weights": _coerce_map(routing.get("kpi_weights")),
        },
        "capabilities": {
            "toolsets_normalized": _normalized_list(toolsets.get("selected", [])),
            "attributes_normalized": _normalized_list(attributes.get("selected", [])),
        },
        "preferences": {
            "autonomy": int(sliders.get("autonomy")) if isinstance(sliders.get("autonomy"), (int, str)) else None,
            "confidence": int(sliders.get("confidence")) if isinstance(sliders.get("confidence"), (int, str)) else None,
            "collaboration": int(sliders.get("collaboration")) if isinstance(sliders.get("collaboration"), (int, str)) else None,
            "communication_style": preferences.get("communication_style"),
            "collaboration_mode": preferences.get("collaboration_mode"),
        },
        "mapping_hints": {
            "neo_agent_config_json": {
                "agent": {"name": name, "version": version},
                "business_function": business_function,
                "role": {
                    "code": role.get("code", ""),
                    "title": role.get("title", ""),
                    "seniority": role.get("seniority", ""),
                    "function": business_function or role.get("function", ""),
                },
                "routing_hints": routing,
                "classification": {"naics": naics} if naics else {},
            },
        },
        "gating": {
            "has_name": bool(name),
            "has_naics": bool(naics.get("code")),
            "has_function": bool(business_function),
            "has_role": bool(role.get("code") or role.get("title")),
        },
    }

    return compiled
