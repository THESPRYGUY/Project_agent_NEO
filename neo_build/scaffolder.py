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
            # time preferences (only if missing)
            if not out.get("time_prefs"):
                out["time_prefs"] = {"timezone": "America/Toronto", "locale": "en-CA", "date_format": "YYYY-MM-DD"}
            # constraints with hard file refs (merge, no overwrite)
            cons = dict(out.get("constraints") or {})
            cons.setdefault("governance_file", PACK_ID_TO_FILENAME[4])
            cons.setdefault("safety_privacy_file", PACK_ID_TO_FILENAME[5])
            cons.setdefault("eval_framework_file", PACK_ID_TO_FILENAME[14])
            cons.setdefault("observability_file", PACK_ID_TO_FILENAME[15])
            out["constraints"] = cons
            # agentic policies
            ap = dict(out.get("agentic_policies") or {})
            reasoning = dict(ap.get("reasoning") or {})
            reasoning.setdefault("disclosure", "Do not expose raw chain-of-thought; provide SoT only.")
            reasoning.setdefault("footprints_spec", PACK_ID_TO_FILENAME[16])
            ap["reasoning"] = reasoning
            routing = dict(ap.get("routing") or {})
            routing.setdefault("workflow_pack", PACK_ID_TO_FILENAME[11])
            routing.setdefault("prompt_pack", PACK_ID_TO_FILENAME[10])
            ap["routing"] = routing
            out["agentic_policies"] = ap
            # refusals
            ref = dict(out.get("refusals") or {})
            ref.setdefault("style", "brief+helpful")
            ref.setdefault("playbooks_source", PACK_ID_TO_FILENAME[5])
            out["refusals"] = ref
            # memory
            mem = dict(out.get("memory") or {})
            mem.setdefault("schema_file", PACK_ID_TO_FILENAME[8])
            mem.setdefault("least_privilege", True)
            mem.setdefault("redact_pii_before_store", True)
            out["memory"] = mem
            # token hygiene
            th = dict(out.get("token_hygiene") or {})
            th.setdefault("budget_enforced", True)
            th.setdefault("prefer_indexes", True)
            th.setdefault("compress_exemplars", True)
            out["token_hygiene"] = th
            # observability
            ob = dict(out.get("observability") or {})
            ob.setdefault("telemetry_spec", PACK_ID_TO_FILENAME[15])
            ob.setdefault("kpi_targets", dict(KPI_TARGETS))
            out["observability"] = ob
            # go live
            gl = dict(out.get("go_live") or {})
            gl.setdefault("lifecycle_pack", PACK_ID_TO_FILENAME[17])
            out["go_live"] = gl
            lang = None
            try:
                langs = list((profile.get("sector_profile") or {}).get("languages") or [])
                lang = langs[0] if langs else None
            except Exception:
                lang = None
            persona = (profile.get("persona") or {}).get("persona_label") if isinstance(profile.get("persona"), Mapping) else None
            tone = (profile.get("persona") or {}).get("tone") if isinstance(profile.get("persona"), Mapping) else None
            dfl = dict(out.get("defaults") or {})
            dfl.setdefault("language", lang or "en")
            dfl.setdefault("persona", persona or "ENTJ")
            dfl.setdefault("tone", tone or "crisp, analytical, executive")
            out["defaults"] = dfl

        elif filename == PACK_ID_TO_FILENAME[3]:  # 03_Operating-Rules_v2.json
            owners = []
            ident = profile.get("identity") if isinstance(profile, Mapping) else None
            if isinstance(ident, Mapping):
                owners = list(ident.get("owners") or [])
            # lifecycle
            if not out.get("lifecycle"):
                out["lifecycle"] = {"states": ["dev", "staging", "prod"], "default": "staging"}
            # escalation
            esc = dict(out.get("escalation") or {})
            actions = list(((profile.get("capabilities_tools") or {}).get("human_gate") or {}).get("actions") or [])
            hg = dict(esc.get("human_gate") or {})
            hg.setdefault("actions", actions)
            esc["human_gate"] = hg
            esc.setdefault("breach_contact", "CAIO")
            out["escalation"] = esc
            # logging
            if not out.get("logging_audit"):
                out["logging_audit"] = {"level": "info", "sink": f"{PACK_ID_TO_FILENAME[15]}#sinks"}
            # rbac merge de-dupe stable
            base_roles = []
            if isinstance(out.get("rbac"), Mapping):
                base_roles = list(out["rbac"].get("roles") or [])
            merged: list[str] = []
            for r in list(base_roles or []) + list(owners or []):
                if r and r not in merged:
                    merged.append(r)
            if merged:
                out["rbac"] = {"roles": merged}

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
            if not out.get("risk_register"):
                out["risk_register"] = entries
            regs = list(((profile.get("sector_profile") or {}).get("regulatory") or []))
            if not out.get("compliance_mapping"):
                out["compliance_mapping"] = {r: {"topic": "TBD", "notes": "Operator to confirm."} for r in regs}
            if not out.get("approvals"):
                out["approvals"] = {"policy_owner": "CAIO", "release_manager": "TeamLead"}

        elif filename == PACK_ID_TO_FILENAME[5]:  # 05_Safety+Privacy_Guardrails_v2.json
            default_class = ((profile.get("governance_eval") or {}).get("classification_default")) or "confidential"
            region = None
            try:
                region = ((profile.get("sector_profile") or {}).get("region") or ["CA"])[0]
            except Exception:
                region = "CA"
            if not out.get("refusal_playbooks"):
                out["refusal_playbooks"] = ["Illegal requests", "Sensitive personal data", "Regulatory evasion"]
            if not out.get("redlines"):
                out["redlines"] = {"prohibited_content": ["malware creation", "doxxing"], "restricted_handling": ["PII", "PCI"]}
            jr = dict(out.get("jurisdictional_rules") or {})
            jr.setdefault("default", region)
            out["jurisdictional_rules"] = jr
            if not out.get("audit_checklist"):
                out["audit_checklist"] = ["Guardrails loaded", "Filters active", "Refusal reasons logged"]
            dc = dict(out.get("data_classification") or {})
            dc.setdefault("default", default_class)
            dc.setdefault("labels", ["public", "internal", "confidential", "restricted"])
            out["data_classification"] = dc

        elif filename == PACK_ID_TO_FILENAME[15]:  # 15_Observability+Telemetry_Spec_v2.json
            # ensure additional anchors populated
            out.setdefault("pii_redaction", {"strategy": "hash+mask"})
            out.setdefault("sampling", {"rate": 1.0})
            out.setdefault("sinks", [{"name": "metrics_stream"}, {"name": "kpi_report_feed"}])
            out.setdefault("dashboards", [{"name": "agent_kpi_overview"}, {"name": "safety_events"}])
            if not out.get("decision_event_fields"):
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
            # Canonical typing for decision event fields
            det = dict(out.get("decision_event_field_types") or {})
            det.setdefault("step_id", "string")
            det.setdefault("persistence_level", "string")
            det.setdefault("band_used", "string")
            det.setdefault("risk", "number")
            det.setdefault("confidence", "number")
            det.setdefault("cost_elapsed", "number")
            det.setdefault("time_elapsed", "number")
            det.setdefault("escalation_flag", "boolean")
            det.setdefault("escalation_reason", "string")
            out["decision_event_field_types"] = det

        elif filename == PACK_ID_TO_FILENAME[17]:  # 17_Lifecycle-Pack_v2.json
            if not out.get("rollback"):
                out["rollback"] = {"on_failure": "revert_to:staging"}
            if not out.get("change_mgmt"):
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
