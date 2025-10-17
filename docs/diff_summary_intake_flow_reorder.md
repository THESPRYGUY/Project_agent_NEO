Diff Summary — Intake Flow Reorder

Modified
- src/neo_agent/intake_app.py — Reordered FORM_TEMPLATE sections; introduced Business Context fieldset; moved Persona Alignment after Function & Role.
- src/ui/generate_agent.js — Updated gating to require agent_name, naics_code, business_function, and role.
- src/ui/persona.js — Added gating: Suggest disabled until role chosen; listen to function/role events.
- README.md — Documented new section order and gating.

Added
- docs/charters/intake_flow_reorder.md — Pinned brief.
- docs/plan_spec_intake_flow_reorder.md — Plan spec.
- docs/arch_spec_intake_flow_reorder.md — Architecture spec.
- docs/adr/ADR-0003-intake-flow-reorder.md — ADR.
- docs/handoff_brief_to_copilot_intake_flow_reorder.md — Handoff brief.
- docs/gate_report_intake_flow_reorder.md — Gate report.
- docs/qc_report_intake_flow_reorder.md — QC report.
- tests/test_generate_gating_contract.py — Browserless contract test.

