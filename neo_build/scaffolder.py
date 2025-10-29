from __future__ import annotations

import os
import datetime as _dt
from typing import Any, Dict, Mapping

from .contracts import CANONICAL_PACK_FILENAMES
from .schemas import required_keys_map


def get_contract_mode() -> str:
    env = str(os.environ.get("NEO_CONTRACT_MODE", "")).strip().lower()
    if env in ("preview", "full"):
        return env
    # Default: CI stays preview to avoid drift; app builds default full
    in_ci = str(os.environ.get("CI", "")).strip().lower() in ("1", "true", "yes", "y")
    return "preview" if in_ci else "full"


def _default_token_budget(filename: str) -> Dict[str, int]:
    # Conservative default; can be tuned per file in a future sprint
    return {"max_output_tokens": 1000}


def _authors(profile: Mapping[str, Any]) -> list[str]:
    ident = profile.get("identity") if isinstance(profile, Mapping) else None
    owners = []
    if isinstance(ident, Mapping):
        owners = list(ident.get("owners") or [])
    if not owners:
        owners = ["CAIO", "CPA", "TeamLead"]
    return owners


def _agent_name(profile: Mapping[str, Any]) -> str:
    ident = profile.get("identity") if isinstance(profile, Mapping) else None
    agent = profile.get("agent") if isinstance(profile, Mapping) else None
    return str((ident or {}).get("agent_id") or (agent or {}).get("name") or "agent")


def build_meta(profile: Mapping[str, Any], filename: str) -> Dict[str, Any]:
    agent = profile.get("agent") if isinstance(profile, Mapping) else None
    version = str((agent or {}).get("version") or "")
    return {
        "agent_id": _agent_name(profile),
        "name": filename,
        "version": version or "v2",
        "created_at": _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "authors": _authors(profile),
    }


def objective_from_profile(profile: Mapping[str, Any], filename: str) -> str:
    rp = profile.get("role_profile") if isinstance(profile, Mapping) else None
    if isinstance(rp, Mapping):
        objs = rp.get("objectives")
        if isinstance(objs, list) and objs:
            return str(objs[0])
    # Fallback to a generic objective
    return f"Contract-scaffolded payload for {filename}"


def schema_keys_for(filename: str) -> list[str]:
    req = required_keys_map().get(filename) or []
    return list(req)


def token_budget_for(profile: Mapping[str, Any], filename: str) -> Dict[str, Any]:
    # Future: profile-driven budgets; for now a conservative default
    return _default_token_budget(filename)


def _default_stub_for_key(key: str) -> Any:
    # Minimal stubs; use array for some plural-ish keys
    list_like = {
        "structure_map",
        "roles_index",
        "recipes",
        "scopes",
        "packs",
        "retention",
        "agents",
        "modules",
        "micro_loops",
        "graphs",
        "engine_adapters",
        "tools",
        "connectors",
        "datasets",
        "secrets",
        "indices",
        "chunking",
        "retrievers",
        "rerankers",
        "embeddings",
        "data_quality",
        "reports",
        "eval_cases",
        "events",
        "sinks",
        "dashboards",
        "alerts",
        "stages",
        "templates",
        "outputs",
        "schedule",
        "policies",
        "prompts",
        "stakeholders",
        "escalations",
        "definition_of_done",
    }
    if key in ("schema_keys",):
        return []
    if key in ("token_budget", "meta"):
        return {}
    if key in ("objective",):
        return ""
    return [] if key in list_like else {}


def enrich_single(profile: Mapping[str, Any], filename: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(payload or {})

    # Ensure core contract keys
    out.setdefault("meta", build_meta(profile, filename))
    out.setdefault("objective", objective_from_profile(profile, filename))
    out.setdefault("schema_keys", schema_keys_for(filename))
    out.setdefault("token_budget", token_budget_for(profile, filename))

    # Ensure other required top-level keys are present as empty stubs
    for key in schema_keys_for(filename):
        if key not in out:
            out[key] = _default_stub_for_key(key)

    return out


def enrich_packs(profile: Mapping[str, Any], packs: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for fname in CANONICAL_PACK_FILENAMES:
        payload = packs.get(fname) if isinstance(packs, Mapping) else None
        out[fname] = enrich_single(profile, fname, payload or {})
    return out

