Title: Enhancement Brief — Intake Flow Reorder (Logical, Gated)
Status: Pinned
Owner: spryg
Repo branch: spryg/Project_agent_NEO#feature/intake-flow-reorder
Stack: Python WSGI, vanilla JS/CSS, file-based catalogs
SLOs: p95 render ≤ 60ms local; memory ≤ 150MB
Data boundaries: local JSON/CSV catalogs; LinkedIn URL is PII; telemetry optional/best-effort

Goal
- Reorder intake UI sections to a logical flow that guarantees required data is collected and passed in the right sequence for optimal agent building.

Proposed Section Order (new)
- Agent Profile: Name, Version
- Business Context: NAICS selector (confirm code/title/level/lineage)
- Business Function & Role: function → role (scoped), defaults preview
- Persona Alignment: suggest/accept persona (uses domain/role context)
- Toolsets: prefilled from function/role defaults; user can adjust
- Attributes & Traits: user picks; can be seeded by persona priors
- Preferences: autonomy/confidence/collaboration sliders; comm style; collab mode
- LinkedIn: optional profile URL (PII)
- Custom Notes: engagement/context notes

Gating Rules
- Generate Agent Repo button enabled only when: Agent name non-empty; NAICS confirmed; Business function selected; Primary role selected
- Persona Suggest/Accept enabled after function/role chosen
- Toolsets/Attributes prefill after role; editable anytime

Acceptance Tests
- Section order renders as above; no broken styles.
- Role dropdown disabled until function chosen; enabled when scoped roles available.
- Generate button disabled until required fields valid; enabled when valid.
- Persona Suggest yields a result after role selected (no runtime errors).
- p95 render ≤ 60ms local; /healthz = OK.

Non-Goals
- Changing role catalog schema or NAICS data.
- Visual redesign beyond minimal spacing/scroll improvements.

Arch Notes — Files and Contracts
- Server template: src/neo_agent/intake_app.py (FORM_TEMPLATE order only); keep existing hidden fields:
  - NAICS: naics_code, naics_title, naics_level, naics_lineage_json
  - Function & Role: business_function, role_code, role_title, role_seniority, routing_defaults_json
- Keep bootstrap for function/role data injection; no API contract change.
- UI modules: src/ui/function_role_picker.html/.js — no contract change.
- Generate button gating: src/ui/generate_agent.js — readiness checks.

Assumptions
- Existing function/role API and picker remain stable; no wiring breaks when moved.
- Persona suggestion depends on role and will have sufficient context after reorder.

Governance
- Confidential by default; record only Summary-of-Thought; track risks, assumptions, rollback.

