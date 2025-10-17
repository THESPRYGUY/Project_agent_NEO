Title: Intake — Reorder Sections + Gated Generate (name+NAICS+function+role)

Summary
- Reorders intake sections to a logical flow and gates the "Generate Agent Repo" action on required inputs. Persona suggestion is gated until a role is selected.

Changes
- Template: Move Business Context (NAICS + Domain) after Agent Profile; move Persona Alignment after Business Function & Role.
- JS: Gating updated in `src/ui/generate_agent.js` to require `agent_name`, `naics_code`, `business_function`, and a role (`role_code` or `role_title`).
- JS: Persona Suggest disabled until role selection; listens to `business:functionChanged` and `role:changed` in `src/ui/persona.js`.
- Docs: plan, arch, ADR, handoff brief, gate+QC reports, and diff summary added. README updated with new order and gating.
- Tests: Added browserless gating contract test `tests/test_generate_gating_contract.py`.

Acceptance
- Section order matches spec; styles intact.
- Role dropdown disabled until function is selected; then enabled with scoped roles.
- Generate button disabled until name+NAICS+function+role present; then enabled.
- Persona Suggest works after role selection.
- /healthz returns OK; p95 render well under 60ms locally.

SLOs
- p95 ≤ 60ms local: met (server log ~4ms render locally).
- Memory ≤ 150MB: unchanged; no heavy assets added.

Contracts
- Hidden fields unchanged: `naics_code`, `naics_title`, `naics_level`, `naics_lineage_json`, `business_function`, `role_code`, `role_title`, `role_seniority`, `routing_defaults_json`.
- No API changes.

Risks
- Potential selector coupling after DOM move mitigated by data-* hooks; no contract changes.

Rollback
- Revert FORM_TEMPLATE and the two JS files; no data migration.

Notes
- Unrelated existing tests may fail (pack loader; telemetry), separate from this change.

