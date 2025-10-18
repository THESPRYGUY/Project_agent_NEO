Plan Spec — Compiled Agent Profile v1

Objective
- Add a compiled, normalized profile payload to improve mapping to the 20‑file agent repo.

Approach
- Introduce `src/neo_agent/profile_compiler.py` with a single pure function `compile_profile`.
- Fields compiled from existing intake values — no contract changes.
- Embed under `_compiled` in the saved profile and emit a sibling `agent_profile.compiled.json`.

Compiled Schema (v1)
- meta: { version: '1.0', generated_at, source: { app_version?, profile_version? } }
- slugs: { agent: '<name-version-slug>' }
- agent: { name, version, persona: { mbti_code, name, description, axes, suggested_traits } }
- business: { function, role: { code, title, seniority }, domain_selector? }
- classification: { naics: { code, title, level, lineage[] } }
- routing: { workflows[], connectors[], report_templates[], autonomy_default, safety_bias, kpi_weights{PRI,HAL,AUD} }
- capabilities: { toolsets_normalized[], attributes_normalized[] }
- preferences: { autonomy, confidence, collaboration, communication_style, collaboration_mode }
- mapping_hints: { neo_agent_config_json: {...}, readme_context: {...} }
- gating: { has_name, has_naics, has_function, has_role }

Tests
- Add `tests/test_profile_compiler.py`: build a profile via app `_build_profile`, compile, and assert presence of `_compiled` and key sections.

Milestones
1) Add docs (this + arch + ADR)
2) Implement compiler + wire into POST `/`
3) Tests + probes
4) Push branch and open PR

Risks
- Accidental contract change: mitigated by adding only, not modifying existing fields.

Rollback
- Remove compiler file and the call-site; `agent_profile.json` remains compatible.

