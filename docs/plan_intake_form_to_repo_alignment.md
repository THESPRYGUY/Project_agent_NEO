# Intake Form → Repo Alignment Plan

## Objectives
- Align Project NEO intake output with the GEN2 master scaffold while preserving NEO’s deterministic 20-pack contract and QA gates.
- Extend the intake UI to collect master-level fields; enrich the builder to consume them; keep parity artifacts and strict gates.

## Scope
- UI intake schema extensions (structured fields + advanced JSON overrides remain).
- Builder mappings across packs 01..20; optional Agent_Manifest.json and INTEGRITY_REPORT.json.
- Tests/CI gates for fail-fast parity (KPI, owners, observability, SoT/retention) + new parity checks.
- Legacy normalization kept via repo_doctor (no changes required).

## Intake Schema Additions
- identity: agent_id, display_name, owners[], no_impersonation
- role_profile: archetype, role_title, role_recipe_ref, objectives[]
- sector_profile: sector, industry, domain_tags[], region[], languages[], risk_tier, regulatory[]
- capabilities_tools:
  - tool_connectors[] { name, enabled, scopes[], secret_ref }
  - human_gate.actions[] (merge with required minimum)
- memory: memory_scopes[], initial_memory_packs[], optional_packs[], data_sources[]
- governance_eval: risk_register_tags[], pii_flags[], classification_default
- advanced_intake_json: freeform JSON paste (deep-merge into profile)

## Builder Mapping (packs)
- 01_README+Directory-Map_v2.json: keep files[]; extract narrative (other keys) and append to README.md.
- 02_Global-Instructions_v2.json: references(16,08,14,15); determinism; effective_autonomy; NAICS context.
- 03_Operating-Rules_v2.json: lifecycle; RBAC; human_gate includes master actions + required minimum.
- 04_Governance+Risk-Register_v2.json: classification_default; regulators; risk_register_tags; pii_flags.
- 05_Safety+Privacy_Guardrails_v2.json: no_impersonation; mask PII; refusal playbooks.
- 06_Role-Recipes_Index_v2.json: role.code/title/seniority; role_recipe_ref; objectives[].
- 07_Subagent_Role-Recipes_v2.json: loop per collaboration_mode (Planner-Builder-Evaluator / Advisory).
- 08_Memory-Schema_v2.json: retention ≤180d; redact flag; memory_scopes; initial_memory_packs.
- 09_Agent-Manifests_Catalog_v2.json: owners ["CAIO","CPA","TeamLead"]; summary sector/region/regulators/NAICS.
- 10_Prompt-Pack_v2.json: guardrails_ref 05; workflow_ref 11; outputs include memo.
- 11_Workflow-Pack_v2.json: graphs include DefaultFlow + requested; gates SST; rollback rule; effective_autonomy.
- 12_Tool+Data-Registry_v2.json: prefer detailed connectors; alias clm→sharepoint, dms→gdrive; least_privilege.
- 13_Knowledge-Graph+RAG_Config_v2.json: indexes include data_sources + default_index; weekly; owner CPA.
- 14_KPI+Evaluation-Framework_v2.json: PRI/HAL/AUD targets; pre-release pipeline.
- 15_Observability+Telemetry_Spec_v2.json: required events/alerts; sinks stubs if present.
- 16_Reasoning-Footprints_Schema_v1.json: SoT required fields; raw CoT never-store.
- 17_Lifecycle-Pack_v2.json: activation_gates mirror 14; rollback to staging.
- 18_Reporting-Pack_v2.json: templates; default field spec [ID, Title, PolicyRef, Severity, Owner, Status, Remediation, LastUpdated]; confidential.
- 19_Overlay-Pack_SME-Domain_v1.json: sector/region/regulators; NAICS code; prompts.
- 20_Overlay-Pack_Enterprise_v1.json: brand voice; legal disclaimer.
- Optional: Agent_Manifest.json (identity/role/sector/NAICS/KPI); INTEGRITY_REPORT.json.

## Tests & CI (incremental)
- Existing 17 tests remain.
- Add assertions:
  - 01 narrative → README; files[] present.
  - 12 connectors carry enabled/scopes/secret_ref when provided; alias mapping present.
  - 04 governance includes risk_register_tags, pii_flags when supplied.
  - 08 memory_scopes & initial_memory_packs; 13 indexes include data_sources.
  - Optional: Agent_Manifest.json coherence.
- CI: continue PASS/FAIL table + legacy coverage CSV for visibility.

## Milestones
1) UI fields skeleton + JSON wiring
2) Builder enrichment + optional parity artifacts
3) Tests extension + documentation updates
4) Parity validation against master scaffold intake

## Risks & Mitigations
- Intake complexity: mitigate with sensible defaults and advanced overrides.
- Legacy variance (dict/list): coercions in validators; repo_doctor normalization.
- Secrets exposure: keep secret_ref placeholders; no live integration.
- Determinism: retain sorted keys, deep-sort lists, newline "\n", UTF‑8 everywhere.

## Acceptance Criteria
- A fresh UI-driven build produces a repo that:
  - Contains the 20 canonical files + README (and optional Agent_Manifest/INTEGRITY_REPORT).
  - Reflects master scaffold data when provided (connectors, memory, governance) with deterministic JSON.
  - Passes all CI tests including new parity assertions.

## Rollback
- Switch back to previous stable branch; remove the new UI fields from render and revert writers.
