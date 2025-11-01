# Assurance Report

## Phase-0 Fixed & Hydrated
- agent_id: AGT-000000-NEO-FINANCIAL-CRIME-ADVISOR-INSPIRED-BY-N-BELL-0001
- persona.code: ENTJ
- persona.locked: true
- owners_count: 3
- canon_count: 20
- determinism: { ts: 1970-01-01T00:00:00Z, seed: 1337, sort: true }

READY: PHASE-0 GREEN â€” SSOT + CANON OK

## Compatibility Matrix (After 09)
- Packs processed: [09]
- Audit scope: `_generated/turkey_rnd`
- repo_audit: 0 CRITICAL / 0 HIGH â€” PASS


## Phase-0.1 SSOT Correction (Turkey R&D)
- agent_id: AGT-112330-TURKEY-RND-0001
- naics.code: 112330
- persona: ENTJ (locked=true)
- owners_count: 3
- governance_eval.gates: { PRI_min:0.95, hallucination_max:0.02, audit_min:0.90 }
- obs.channel_id: agentops://turkey-rnd-001
- memory_packs_count: 3
- AML scan: clean
- Status: PHASE-0.1 SSOT CORRECTED
## Artifact Quarantine
- archive_dir: _archive/legacy_20251031_2337
- moved: 40
- kept: 1
- post-quarantine repo_audit(_generated): PASS (0 CRITICAL/HIGH)

## Phase-1: 02_Global-Instructions_v2.json
Inputs: SSOT(ref/intake/agent_profile.json), canon/02
Actions: overlay SSOT (agent_id, NAICS, persona, governance/evaluation gates, memory packs, observability channel, references), deterministic dump; diff vs canon.
Checks:
- contract_validate_one: ?
- repo_audit(_generated): 0 CRITICAL/HIGH — PASS
Result: 02 finalized.

## Compatibility Matrix (After {04,05,03})
- 03.logging_audit.sink_id in 15.sinks: PENDING (15 canon lacks sinks; will assert when 15 is built)
- 03.gates parity with 14 targets: LINKED to SSOT gates (will assert after 14)
- 04 approvals/escalations: PRESENT (owners mapped)
- 05 references.governance ? 04: OK
- repo_audit(_generated): 0 CRITICAL/HIGH — PASS

### Rationale: 04_Governance+Risk-Register_v2.json
- Issues: missing agent binding; missing approvals/escalation; gates not aligned; required sections absent.
- Decisions: set meta.agent_id; map owners?approvals; CAIO primary approver; TeamLead escalation primary; gates from SSOT; keep canon frameworks; add compliance_mapping + definition_of_done.
- Tests: contract_validate_one ?; repo_audit ?
- Result: Generated and diffed deterministically.

### Rationale: 05_Safety+Privacy_Guardrails_v2.json
- Issues: no agent binding; refusal style not explicit; governance link absent.
- Decisions: set meta.agent_id; refusal_style.default; privacy.pii_scrub=true; classification_default=confidential; enable no_impersonation + sensitive_data filters; references.governance=04; add operational_hooks + audit_checklist.
- Tests: contract_validate_one ?; repo_audit ?
- Result: Generated and diffed deterministically.

### Rationale: 03_Operating-Rules_v2.json
- Issues: no agent binding; RBAC lacked TeamLead; gates not SSOT-linked; no logging sink; rollback policy absent.
- Decisions: set meta.agent_id; merge owners into rbac.roles; set gates from SSOT; logging_audit.sink_id=agentops://turkey-rnd-001; rollback.on_gate_fail=true; references wired to 04/05/15/14/17.
- Tests: contract_validate_one ?; repo_audit ?
- Result: Generated and diffed deterministically.

### Rationale: 06_Role-Recipes_Index_v2.json
- Inputs: SSOT(agent_id, persona=ENTJ, slug=turkey-rnd), canon/06.
- Actions: meta.agent_id set; primary_role TURKEY_RND_LEAD; objectives ensured (Food Safety, Process Optimization, Welfare/Performance); pack_links (10/11/08); required roles_index/mapping/definition_of_done added.
- Checks: contract_validate_one ?; repo_audit ?.

### Rationale: 07_Subagent_Role-Recipes_v2.json
- Inputs: SSOT(agent_id), 06 primary_role_code, canon/07.
- Actions: meta.agent_id set; persona=ENTJ; link_to_index.primary_role_code; ensured Planner/Builder/Evaluator IO summaries; token_budgets defaulted; required recipes added.
- Checks: contract_validate_one ?; repo_audit ?.

### Rationale: 08_Memory-Schema_v2.json
- Inputs: SSOT(agent_id, memory.initial_memory_packs), canon/08.
- Actions: meta.agent_id set; packs.initial from SSOT (3 seeds); scopes set; pii_redaction.strategy=hash+mask; sync_allowlist conservative; retrieval.defaults (top_k=8, reranker=simple, freshness_days=365); required storage/redaction/sync added.
- Checks: contract_validate_one ?; repo_audit ?.

## Compatibility Matrix (After {06,07,08})
- 06.primary_role_code present: TURKEY_RND_LEAD; 07.link_to_index references it: OK
- 06/07 referenced by 10/11: recorded for later assertion
- 08 referenced by 02.memory_schema and future 10/11: OK (02.references.memory_schema set)
- repo_audit(_generated): 0 CRITICAL/HIGH — PASS

### Pack 19 â€” 19_Overlay-Pack_SME-Domain_v1.json (@ 2025-11-01T19:26:57Z)
- Deterministic overlay from SSOT
- No artifacts staged
- Review: schema & cross-refs match canon

