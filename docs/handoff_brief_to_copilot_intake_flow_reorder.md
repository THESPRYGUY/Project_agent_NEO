Handoff Brief — Intake Flow Reorder

Summary
- Reordered FORM_TEMPLATE and updated gating. Keep types/contracts intact. Minimal diffs in one Python template and two JS files.

Implement
- src/neo_agent/intake_app.py: move NAICS into a new Business Context fieldset (with Domain selector), move Persona section after Business Function & Role.
- src/ui/generate_agent.js: gate Generate Agent Repo on agent_name, naics_code, business_function, role_code/role_title.
- src/ui/persona.js: disable Suggest until role selected; enable on role:changed; Accept still enabled after suggestion.

Tests
- Keep Python smoke tests.
- Add test_generate_gating_contract.py: assert generate_agent.js contains gating tokens for name, NAICS, function, role.

Perf
- No large assets added. Expect p95 render < 60ms.

Checklist
- No schema changes to catalogs.
- No API changes.
- Keep data-* selectors intact.
- Ensure Generate button starts disabled.
- Validate /healthz.

