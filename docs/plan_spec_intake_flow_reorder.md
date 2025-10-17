Plan Spec — Intake Flow Reorder

Objective
- Reorder sections and enforce gating for NAICS/function/role/name while preserving existing contracts and keeping diffs small.

Workflow
- Ingest → Plan → Design → Validate → Handoff → Review

Scope
- Update server-side FORM_TEMPLATE order only.
- Update generate gating (JS) and persona gating (JS) based on function/role.
- Add a tiny browserless test to assert gating contract.
- Update README notes with the new order and gating rules.

Out of Scope
- Schema changes to catalogs; NAICS content; any visual redesign beyond spacing/scroll tweaks.

Assumptions
- function_role JS dispatches business:functionChanged and role:changed; selectors do not depend on position.
- Persona suggestion should be disabled until a role is selected.

Deliverables
- patch_set, tests, polish, qc_report, diff_summary
- Docs: arch_spec, ADR, handoff_brief_to_copilot, gate_report

Constraints / SLOs
- p95 initial render ≤ 60ms local; memory ≤ 150MB.

Milestones & Gates
1) Design docs ready (this file + arch_spec + ADR) — Gate: reviewable
2) Minimal diffs applied — Gate: unit smoke tests green
3) Probes run (/healthz, root render) — Gate: OK
4) Handoff brief prepared — Gate: ready for Copilot implementation polish

Acceptance Tests (from brief)
- Section order renders per spec; no broken styles
- Role dropdown disabled until function chosen; enabled when roles scoped
- Generate button disabled until agent name + NAICS + function + role present
- Persona Suggest enabled and yields result after selecting role
- /healthz responds OK

Risks
- Moving DOM fragments could break query selectors: mitigated by relying on data-* hooks.
- Gating could become over-zealous and block flows: mitigated by minimal conditions and tests.

Rollback
- Revert FORM_TEMPLATE block and revert gating edits to generate_agent.js and persona.js.

