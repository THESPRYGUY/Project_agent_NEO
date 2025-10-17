ADR 0004: Compiled Agent Profile v1

Status: Accepted
Date: 2025-10-17

Context
The raw form profile is faithful to inputs but not optimized for downstream templating across the 20‑file agent repo. Repeated merging and normalization increases coupling and latency.

Decision
Add a compiled profile alongside the raw manifest. Compute slugs, merge routing defaults, normalize capabilities/attributes, and extract persona/NAICS/function-role into stable typed blocks. Embed under `_compiled` and save a sibling `agent_profile.compiled.json`.

Consequences
Simpler mapping to repo files; spec/repo generators can adopt the compiled view incrementally. No breaking changes to existing consumers.

Rollback
Remove the compiler and compiled emission; raw `agent_profile.json` remains intact.

