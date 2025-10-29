from __future__ import annotations

import os
import datetime as _dt
from typing import Any, Dict, Mapping

from .contracts import CANONICAL_PACK_FILENAMES, PACK_ID_TO_FILENAME, KPI_TARGETS
from .schemas import required_keys_map


def get_contract_mode() -> str:
    """Resolve contract mode with CI hardening.

    Priority:
      1) Explicit override via NEO_CONTRACT_MODE={preview|full}
      2) CI detection via CI=1|true|True or GITHUB_ACTIONS=true
      3) Default to full locally
    """
    env = str(os.environ.get("NEO_CONTRACT_MODE", "")).strip().lower()
    if env in ("preview", "full"):
        return env
    ci_val = str(os.environ.get("CI", "")).strip().lower()
    ga_val = str(os.environ.get("GITHUB_ACTIONS", "")).strip().lower()
    in_ci = (ci_val in ("1", "true", "yes", "y")) or (ga_val in ("1", "true", "yes", "y"))
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
    # Sorted for stability
    return sorted(set(req))


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
    # Enforce schema_keys exactness and stable ordering
    out["schema_keys"] = schema_keys_for(filename)
    out.setdefault("token_budget", token_budget_for(profile, filename))

    # Ensure other required top-level keys are present as empty stubs
    for key in schema_keys_for(filename):
        if key not in out:
            out[key] = _default_stub_for_key(key)

    # Populate specific content for key packs (full mode enrichment)
    try:
        if filename == PACK_ID_TO_FILENAME[2]:  # 02_Global-Instructions_v2.json
            # time preferences
            out["time_prefs"] = {"timezone": "America/Toronto", "locale": "en-CA", "date_format": "YYYY-MM-DD"}
            # constraints with hard file refs
            out["constraints"] = {
                "governance_file": PACK_ID_TO_FILENAME[4],
                "safety_privacy_file": PACK_ID_TO_FILENAME[5],
                "eval_framework_file": PACK_ID_TO_FILENAME[14],
                "observability_file": PACK_ID_TO_FILENAME[15],
            }
            out["agentic_policies"] = {
                "reasoning": {
                    "disclosure": "Do not expose raw chain-of-thought; provide SoT only.",
                    "footprints_spec": PACK_ID_TO_FILENAME[16],
                },
                "routing": {
                    "workflow_pack": PACK_ID_TO_FILENAME[11],
                    "prompt_pack": PACK_ID_TO_FILENAME[10],
                },
            }
            out["refusals"] = {"style": "brief+helpful", "playbooks_source": PACK_ID_TO_FILENAME[5]}
            out["memory"] = {"schema_file": PACK_ID_TO_FILENAME[8], "least_privilege": True, "redact_pii_before_store": True}
            out["token_hygiene"] = {"budget_enforced": True, "prefer_indexes": True, "compress_exemplars": True}
            out["observability"] = {"telemetry_spec": PACK_ID_TO_FILENAME[15], "kpi_targets": dict(KPI_TARGETS)}
            out["go_live"] = {"lifecycle_pack": PACK_ID_TO_FILENAME[17]}
            lang = None
            try:
                langs = list((profile.get("sector_profile") or {}).get("languages") or [])
                lang = langs[0] if langs else None
            except Exception:
                lang = None
            persona = (profile.get("persona") or {}).get("persona_label") if isinstance(profile.get("persona"), Mapping) else None
            tone = (profile.get("persona") or {}).get("tone") if isinstance(profile.get("persona"), Mapping) else None
            out["defaults"] = {"language": lang or "en", "persona": persona or "ENTJ", "tone": tone or "crisp, analytical, executive"}

        elif filename == PACK_ID_TO_FILENAME[3]:  # 03_Operating-Rules_v2.json
            owners = []
            ident = profile.get("identity") if isinstance(profile, Mapping) else None
            if isinstance(ident, Mapping):
                owners = list(ident.get("owners") or [])
            # lifecycle
            out["lifecycle"] = {"states": ["dev", "staging", "prod"], "default": "staging"}
            # escalation
            actions = list(((profile.get("capabilities_tools") or {}).get("human_gate") or {}).get("actions") or [])
            out["escalation"] = {"human_gate": {"actions": actions}, "breach_contact": "CAIO"}
            # logging
            out["logging_audit"] = {"level": "info", "sink": f"{PACK_ID_TO_FILENAME[15]}#sinks"}
            # rbac
            base_roles = out.get("rbac", {}).get("roles") if isinstance(out.get("rbac"), Mapping) else []
            roles = list(base_roles or [])
            for o in owners:
                if o not in roles:
                    roles.append(o)
            if roles:
                out["rbac"] = {"roles": roles}

        elif filename == PACK_ID_TO_FILENAME[4]:  # 04_Governance+Risk-Register_v2.json
            # risk register entries
            tags = list(((profile.get("governance_eval") or {}).get("risk_register_tags") or []))
            entries = []
            for i, t in enumerate(tags or ["model_quality", "data_privacy"]):
                entries.append({
                    "id": f"RK-{i+1:03d}",
                    "tag": t,
                    "owner": "CAIO",
                    "mitigation": "TBD",
                })
            out["risk_register"] = entries
            regs = list(((profile.get("sector_profile") or {}).get("regulatory") or []))
            out["compliance_mapping"] = {r: {"topic": "TBD", "notes": "Operator to confirm."} for r in regs}
            out["approvals"] = {"policy_owner": "CAIO", "release_manager": "TeamLead"}

        elif filename == PACK_ID_TO_FILENAME[5]:  # 05_Safety+Privacy_Guardrails_v2.json
            default_class = ((profile.get("governance_eval") or {}).get("classification_default")) or "confidential"
            region = None
            try:
                region = ((profile.get("sector_profile") or {}).get("region") or ["CA"])[0]
            except Exception:
                region = "CA"
            out["refusal_playbooks"] = ["Illegal requests", "Sensitive personal data", "Regulatory evasion"]
            out["redlines"] = {"prohibited_content": ["malware creation", "doxxing"], "restricted_handling": ["PII", "PCI"]}
            out["jurisdictional_rules"] = {"default": region}
            out["audit_checklist"] = ["Guardrails loaded", "Filters active", "Refusal reasons logged"]
            out["data_classification"] = {"default": default_class, "labels": ["public", "internal", "confidential", "restricted"]}

        elif filename == PACK_ID_TO_FILENAME[15]:  # 15_Observability+Telemetry_Spec_v2.json
            # ensure additional anchors populated
            out.setdefault("pii_redaction", {"strategy": "hash+mask"})
            out.setdefault("sampling", {"rate": 1.0})
            out.setdefault("sinks", [{"name": "metrics_stream"}, {"name": "kpi_report_feed"}])
            out.setdefault("dashboards", [{"name": "agent_kpi_overview"}, {"name": "safety_events"}])
            out["decision_event_fields"] = [
                "step_id",
                "persistence_level",
                "band_used",
                "risk",
                "confidence",
                "cost_elapsed",
                "time_elapsed",
                "escalation_flag",
                "escalation_reason",
            ]

        elif filename == PACK_ID_TO_FILENAME[17]:  # 17_Lifecycle-Pack_v2.json
            out["rollback"] = {"on_failure": "revert_to:staging"}
            out["change_mgmt"] = {"approver": "CAIO", "record": "change_log.md"}
    except Exception:
        # Non-fatal; enrichment should never crash writes
        pass

    return out


def enrich_packs(profile: Mapping[str, Any], packs: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for fname in CANONICAL_PACK_FILENAMES:
        payload = packs.get(fname) if isinstance(packs, Mapping) else None
        out[fname] = enrich_single(profile, fname, payload or {})
    return out
