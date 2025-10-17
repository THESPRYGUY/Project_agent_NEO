Architecture Spec — Intake Flow Reorder

Current
- Single-file WSGI app assembles the intake HTML from template blocks in src/neo_agent/intake_app.py.
- UI assets are plain HTML/CSS/JS in src/ui, injected verbatim.
- Function/Role picker provides hidden inputs: business_function, role_code, role_title, role_seniority, routing_defaults_json and dispatches custom events (business:functionChanged, role:changed).
- NAICS selector writes hidden naics_* fields and provides a confirm action.
- Persona module relies on role/domain context but is currently positioned before role selection.

Proposed
- Form section order:
  1) Agent Profile
  2) Business Context (NAICS + Domain selector block consolidated)
  3) Business Function & Role
  4) Persona Alignment
  5) Toolsets
  6) Attributes & Traits
  7) Preferences
  8) LinkedIn
  9) Custom Notes

Contracts (no change)
- Keep hidden fields as-is: naics_code, naics_title, naics_level, naics_lineage_json, business_function, role_code, role_title, role_seniority, routing_defaults_json.
- Keep function/role bootstrap mechanism intact.
- No API path changes.

Gating Logic
- Generate Agent Repo enabled when all hold:
  - agent_name non-empty
  - naics_code set (confirmed)
  - business_function non-empty
  - role present (role_code or role_title)
- Persona Suggest disabled until role is selected (enable on role:changed).

Performance
- DOM order change only + tiny JS checks; no heavy computation added.
- Expect p95 render < 60ms. Assets unchanged in size.

Failure Modes / Handling
- Missing assets: intake_app safe reads already tolerate missing files.
- Invalid JSON in hidden fields: generate_agent.js parses with try/catch and ignores errors.
- Persona suggestion without role: button stays disabled; summary prompts user.

Testing Strategy
- Keep Python server smoke tests.
- Add a browserless contract test asserting gating code checks for name, NAICS, function, role.
- Manual probe: ensure initial Generate button is disabled; enable after setting fields in UI.

Diff Boundaries
- src/neo_agent/intake_app.py (FORM_TEMPLATE order only)
- src/ui/generate_agent.js (gating readiness)
- src/ui/persona.js (enable/disable Suggest)
- tests/test_generate_gating_contract.py (new)

