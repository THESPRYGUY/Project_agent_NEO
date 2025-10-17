Architecture Spec — Compiled Agent Profile v1

Current Flow
- Intake builds `profile` in `_build_profile` and saves `agent_profile.json`.
- Spec generator consumes the raw profile to produce `agent_config.json`, `agent_manifest.json`, and `agent_preferences.json`.
- Repo generator takes a subset to scaffold a minimal repo.

Change
- Add `profile_compiler.compile_profile(profile)` and call it in the POST `/` handler before saving.
- Embed the result as `profile['_compiled']` and write `agent_profile.compiled.json`.

Key Transformations
- Slug: deterministic slug from name/version
- Persona: extract enriched MBTI metadata (reuse logic from spec generator)
- Function/Role: typed block with code/title/seniority
- Routing defaults: merged from `routing_defaults_json` hidden field
- NAICS: code/title/level/lineage normalized
- Capabilities: snake_case toolsets and attributes for easy templating
- Preferences: numeric sliders + modes
- Mapping hints: preformed JSON blocks that match repo generator inputs
- Gating snapshot: booleans for generate preconditions

Performance
- Pure Python dictionary operations; negligible overhead (< 1ms on local)

Compatibility
- Existing JSON shape unchanged; only adds `_compiled` and a new file.

