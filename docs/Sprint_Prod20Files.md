# Sprint: Productionization (20 Files)

| File | GEN2 Archetype Path | Generated Path | Intake Fields â†’ Keys | Gaps/Blanks | Final Decisions | Tests/Checks | Status |
| - | - | - | - | - | - | - | - |

| 09_Agent-Manifests_Catalog_v2.json | agent_id, owners, observability.paths | canon?turkey-R&D values | repo_audit (local pack) | ? |
| 02_Global-Instructions_v2.json | agent_id, gates, references, observability.default_channel_id | SSOT overlay?deterministic dump | contract_validate_one + repo_audit | ? |
| 04_Governance+Risk-Register_v2.json | agent_id, owners?approvals/escalation, gates, refs | SSOT overlay; add compliance_mapping & DoD | contract_validate_one + repo_audit | ? |
| 05_Safety+Privacy_Guardrails_v2.json | agent_id, refusal_style, privacy.pii_scrub, refs | SSOT overlay; enable filters; add hooks/audit | contract_validate_one + repo_audit | ? |
| 03_Operating-Rules_v2.json | agent_id, rbac.roles?owners, gates, logging.sink_id, refs | SSOT overlay; add rollback.on_gate_fail | contract_validate_one + repo_audit | ? |
| 06_Role-Recipes_Index_v2.json | primary_role, pack_links, roles_index/mapping | SSOT overlay; ensure objectives; add required keys | contract_validate_one + repo_audit | ? |
| 07_Subagent_Role-Recipes_v2.json | planner/builder/evaluator IO + budgets | SSOT overlay; link_to_index; add recipes | contract_validate_one + repo_audit | ? |
| 08_Memory-Schema_v2.json | packs.initial, scopes, retrieval.defaults | SSOT overlay; add storage/redaction/sync | contract_validate_one + repo_audit | ? |
| 19_Overlay-Pack_SME-Domain_v1.json | SSOT→meta.agent_id | Deterministic overlay + schema guard | contract_validate/repo_audit | READY |
| 17_Lifecycle-Pack_v2.json | SSOTâ†’meta.agent_id | Deterministic overlay + schema guard | contract_validate/repo_audit | READY |
| 16_Reasoning-Footprints_Schema_v1.json | SSOTâ†’meta.agent_id | Deterministic overlay + schema guard | contract_validate/repo_audit | READY |


| 18_Reporting-Pack_v2.json | SSOT→meta.agent_id | Deterministic overlay + schema guard | contract_validate/repo_audit | READY |
| 17_Lifecycle-Pack_v2.json | SSOTâ†’meta.agent_id | Deterministic overlay + schema guard | contract_validate/repo_audit | READY |
| 16_Reasoning-Footprints_Schema_v1.json | SSOTâ†’meta.agent_id | Deterministic overlay + schema guard | contract_validate/repo_audit | READY |


