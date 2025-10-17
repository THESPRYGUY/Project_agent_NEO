Title: Enhancement — Compiled Agent Profile (v1)
Status: Proposed
Owner: spryg
Repo branch: spryg/Project_agent_NEO#feature/compiled-profile-v1
Stack: Python WSGI, vanilla JS/CSS, file-based catalogs
SLOs: p95 render ≤ 60ms local; memory ≤ 150MB
Data boundaries: local JSON/CSV catalogs; LinkedIn URL PII; telemetry optional/best-effort

Goal
- Produce a canonical, compiled agent profile from the intake form that is optimized for mapping to the Project Agent NEO 20‑file agent repo.

Rationale
- The current `agent_profile.json` preserves raw form selections. Downstream generation benefits from a normalized, typed, denormalized “compiled” view with routing/defaults merged, slugs computed, and stable keys for file templating.

Deliverables
- profile_compiler module providing `compile_profile(profile)->dict`
- Embed `_compiled` in `agent_profile.json`
- Write `agent_profile.compiled.json` alongside the raw profile
- Minimal tests asserting presence and basic shape
- Docs: plan_spec, arch_spec, ADR, handoff, gate report

Non‑Goals
- Changing existing intake fields or API contracts
- Rewriting the spec/repo generators (they can gradually adopt the compiled view)

Acceptance
- POST `/` writes both `agent_profile.json` and `agent_profile.compiled.json`
- `_compiled` block present and stable
- Tests green; probes OK

