# AGENTS.md — Project NEO Agent Guide

**Purpose**  
How to define an agent with the intake form, validate it, and generate the full 20-file pack.

## 1) Agent Profile: required fields
- **Persona**: `{ name, mbti? }`
- **Domain**: Top Level → Subdomain → tags[]  
  If Top Level = **Sector Domains** and Subdomain ≠ “Multi-Sector SME Overlay”, include **NAICS**:
  ```json
  {"code":"51821","title":"Data processing, hosting, and related services","level":5,"version":"NAICS 2022 v1.0","path":["51","518","5182","51821"]}
  ```

Toolsets (normalized payload)

{
  "capabilities": ["reasoning_planning","data_rag","orchestration"],
  "connectors": [{"name":"notion","scopes":["read:db/*","write:tasks"]}],
  "governance": {"storage":"kv","redaction":["mask_pii","never_store_secrets"],"retention":"default_365","data_residency":"auto"},
  "ops": {"env":"staging","dry_run":true,"latency_slo_ms":1200,"cost_budget_usd":5.0}
}


Traits: weighted 0–100 with provenance (manual|mbti_suggested|mbti_suggested+edited)

Preferences: sliders (0–100, step 5) + dropdowns; derived knobs are computed on save:

"prefs_knobs":{"confirmation_gate":"light","rec_depth":"balanced","handoff_freq":"medium", ...}


Schemas: /schemas/profile.schema.json, toolsets.schema.json, preferences.schema.json, traits.schema.json.

2) Validate & Build (20-file repo)

Validate

curl -sS localhost:5000/api/profile/validate -X POST -H 'Content-Type: application/json' -d @profile.json | jq


Dry-Run

curl -sS localhost:5000/api/repo/dry_run -X POST -H 'Content-Type: application/json' -d '{"profile":<PROFILE_JSON>,"options":{"include_examples":false,"git_init":true,"zip":true,"overwrite":"safe"}}' | jq


Build

curl -sS localhost:5000/api/repo/build -X POST -H 'Content-Type: application/json' -d '{"profile":<PROFILE_JSON>,"options":{"include_examples":false,"git_init":true,"zip":true,"overwrite":"safe"}}' | jq


Outputs: generated/neo_agent_<slug>/ with the 20 canonical files, README_intro.md, manifest.json (stable hashes), optional ZIP.

3) Telemetry

Domain/NAICS: domain:*, naics:*

Traits: traits:*

Preferences: prefs:*

Toolsets: toolsets:*

Repo build: repo:validate|repo:render|repo:package|repo:done|repo:error

4) Tests

pytest

bun tests/repo_builder_panel.spec.ts  # and other panel specs if present

5) Governance guardrails

Redaction flags are immutable: ["mask_pii","never_store_secrets"]

Least-privilege connector scopes; CAIO approval banner for non-default scopes

Classification: confidential; SoT disclaimer in README
