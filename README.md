# Project Agent NEO â€” Quickstart & Onboarding

Status: Release 2.1.2-dev (post v2.1.1)

Project Agent NEO is a governed, test-driven scaffold for generating and validating a 20-pack agent repository from a v3 intake. It emphasizes strict KPI parity, observability, and safe reasoning footprints while remaining model/vendor agnostic.

## 1) What is Project Agent NEO
One-paragraph: NEO provides a reproducible intake â†’ build â†’ validate pipeline producing a canonical 20-file agent repo. It ships a simple WSGI service, UI helpers, builders/validators, and CI gates (parity, golden snapshot, smoke) to ensure deterministic, auditable outputs for any use-case.

## 2) TL;DR Quickstart (5 minutes)
Copy env and run local compose, then hit health:

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up --build
# In another shell
curl -i http://127.0.0.1:5000/health
```

You should see HTTP 200 with headers `X-NEO-Intake-Version` and `X-Commit-SHA`.

## How the Intake works now
1. Contract schema (v1) loads from `/api/intake/schema` at runtime.
2. Memory, connectors, governance, and RBAC chips derive from packs 03/04/05/08/12.
3. Hidden form inputs stay in sync with the Intake Contract panel state.
4. Dry-run triggers `tools/apply_intake.py --dry-run` and surfaces Mapping + Diff reports.
5. Apply runs the mapper and displays the changed pack list.
6. Validation errors sort deterministically across multi-error payloads.
7. CI gates flow schema-validate -> intake-mapper-guard -> placeholder-sweep -> repo-audit -> unit -> ui-schema-smoke.
8. `scripts/ui_schema_smoke.py` smoke-tests the panel payload in CI.
9. Sample payload lives at [`data/intake_contract_v1_sample.json`](data/intake_contract_v1_sample.json).
10. Connector secrets remain sanitized; retention/permissions default from pack 08.

### Governance Cross-Pack Check
Run the governance cross-pack check to keep packs 02, 04, and 05 aligned.
Invoke from repo root: `python scripts/check_governance_crosspack.py --root generated_repos/agent-build-007-2-1-1`.
Pass any directory that contains the three pack files if you need to target another build.
The script confirms 02 constraints and refusal playbooks point to the actual governance and safety pack names.
It checks 04 privacy_alignment.guardrails_file and 05 operational_hooks.governance_file point back correctly.
Classification defaults must agree across 04 (root and policy) and 05 data_classification, otherwise the run fails.
No-impersonation must stay true in both packs; the checker flags mismatches immediately.
PII flags must match across packs and cannot mix 'none' with other entries.
Use --root generated_repos to scan every generated repo, and add --fail-fast to stop at the first failing repo.

### Registry Enum Sourcing
- Enum choices for connectors, data sources, and datasets resolve via `neo_agent.registry_loader.load_tool_registry`.
- The loader prefers `NEO_REGISTRY_ROOT`, then `_generated/_last_build.json`, before falling back to the baseline packs.
- Pack `12_Tool+Data-Registry_v2.json` remains the single source of truth for connector/dataset IDs.
- `/api/intake/schema` hydrates UI pickers with the loader output on every request.
- Intake contract defaults no longer rely on checked-in JSON fragments for governed fields.
- Front-end chips and toggles reflect loader data, while hidden inputs mirror the selected IDs.
- Dataset chips surface loader IDs for operator review without mutating the contract payload.
- CI job `registry-consistency` diffs sample payload IDs against pack 12 to catch drift.
- Updating the pack snapshot is enough to refresh the UI and mapper defaults.
- Registry alignment checks run in under a second and fail fast on unknown or missing IDs.

## 3) Dev Setup (10 minutes)
- Python 3.11 and Node 20.x
- Install and run tests:

```bash
python -m pip install -U pip
pip install -e .[dev]
pytest -q -vv

npm ci
npm test
```

## 4) CI Matrix (Required + Advisory)
Required checks (enforced in PRs):
- unit-python (coverage)
- unit-js (Vitest thresholds)
- golden snapshot
- docker-build-smoke
- smoke (strict parity ON)
- contract-validate (contract+parity crossrefs)

Advisory/non-blocking:
- Integration tests (-m integ)
- Docs check (SCA warn-only and optional markdown lint)

## 5) Parity, Contracts & Golden Snapshot
- Parity model: KPI targets from intake must match across 02 vs 14; propagated to 03/11/17. CI treats mismatches as blocking.
- Golden snapshot: builds from ixtures/intake_v3_golden.json and verifies byte-for-byte equality with ixtures/expected_pack_golden/*. Diff artifacts uploaded under _artifacts/golden-diff/** on failure.

## 6) Release Flow
Tags `v*` trigger the release workflow:
- Build container, smoke `/health`, generate integrity artifacts
- Attach to release: `repo.zip`, `INTEGRITY_REPORT.json`, `build.json`

## 7) Security Posture

See `SECURITY.md` for the full policy and reporting process.

Supported Versions

| Component | Version |
| - | - |
| Python | 3.11 |
| Node.js | 20.x |
- Dependency pinning: Python constraints and Node lockfile; SCA runs warn-only in CI and uploads reports
- Optional auth stub (default OFF): when `AUTH_REQUIRED=true`, all non-`/health` routes require `Authorization: Bearer <token>`; 401 JSON envelope returned on missing/invalid tokens
- â€œNo secrets/PII in logsâ€ policy

## 8) Troubleshooting
- Line endings: normalize to `\n` in snapshots to avoid diffs
- Env flags: set `FAIL_ON_PARITY=true` to enforce hard parity gates locally; `NEO_APPLY_OVERLAYS=false` for baseline runs
- Docker bind issues on Windows: prefer WSL2 backend; ensure `.env` exists

## Features

- **Deterministic configuration** â€“ dataclass based models with JSON helpers keep
  runtime settings predictable.
- **Conversation aware state** â€“ a structured conversation history is maintained for
  every dispatch, enabling downstream analysis.
- **Modular skills** â€“ skills are simple callables that can be dynamically discovered
  from configuration entrypoints.
- **Planning pipeline** â€“ the runtime produces a basic plan and executes each step
  through a configurable pipeline.
- **Observability** â€“ event emission and telemetry utilities capture metrics during
  execution.

## Usage

```bash
pip install -e .[dev]
neo-agent --config path/to/config.json
```

If no configuration path is supplied, the default configuration containing the `echo`
skill will be used. Dispatches can be driven programmatically via the
`neo_agent.AgentRuntime` class:

```python
from neo_agent import AgentConfiguration, AgentRuntime

runtime = AgentRuntime(AgentConfiguration.default())
runtime.initialize()
result = runtime.dispatch({"input": "Ping"})
print(result["echo"])  # -> "Ping"
```

### Custom agent intake page

Launch the customizable intake experience using the bundled WSGI server to produce
tailored agent profiles and spec files:

```bash
python -m neo_agent.intake_app
```

Open http://127.0.0.1:5000/ to select the agent domain, role, toolsets, attributes,
and behavioral sliders. The form also accepts a LinkedIn profile URL; available
metadata is scraped and merged with the manual selections. Submitting the form
creates `agent_profile.json` and, after Build, writes the single source of truth (SoT)
pack under `_generated/<AGENT_ID>/<UTC_TS>/`. Spec previews are written alongside the
SoT under `<outdir>/spec_preview/`. Deprecation: references to `generated_specs/` are
deprecated for one release. A 307 shim redirects legacy requests to the latest
`<outdir>/spec_preview/`.
derived configuration and metadata artifacts used by the generator.

#### Intake Section Order & Gating
- Order: Agent Profile â†’ Business Context (NAICS + Domain) â†’ Business Function & Role â†’ Persona Alignment â†’ Toolsets â†’ Attributes â†’ Preferences â†’ LinkedIn â†’ Custom Notes
- Generate Agent Repo is enabled only when: agent_name, NAICS, business_function, and role are all set.
- Persona Suggest is enabled after choosing a role.

## Testing

The repository relies on `pytest` for test execution:

```bash
pytest
```

Node UI utils use `vitest` for lightweight tests:

```bash
npm test
```

### Testing & CI

- Pytest markers: `unit` (default), `integ`, `smoke`.
- Default `pytest` runs only unit tests; use `pytest -m integ` for integration.
- Python coverage enforced via `.coveragerc` (fail_under=85). CI runs `coverage run -m pytest` then `coverage report`.
- Vitest covers `tests/unit_js/**` with thresholds: lines 80, functions 80, statements 80, branches 70 (see `vitest.config.ts`).
- CI gates: unit-python and unit-js are required; integration is advisory; smoke runs via `python ci/smoke.py` and must pass.

## Smoke Test

Run the end-to-end smoke locally (builds a canonical 20-pack repo, emits artifacts):

```bash
make smoke
```

Artifacts are written to `_artifacts/smoke/`:
- `repo.zip` â€” zipped generated repo
- `INTEGRITY_REPORT.json` â€” integrity + parity summary
- `build.json` â€” CI-parsed summary with `file_count`, `parity`, `integrity_errors`

The command prints a one-line status, for example:

```
✅ SMOKE OK | files=20 | parity=ALL_TRUE | integrity_errors=0
```

### Strict Parity in CI

- Gate: CI enforces KPI parity as a hard gate with `FAIL_ON_PARITY=true` across all jobs.
- Artifacts: job uploads `_artifacts/**`, `**/INTEGRITY_REPORT.json`, `**/build.json`, and any `**/*.zip` on every run (pass/fail).
- PR Summary: CI posts a one-line outcome. Green shows:
  - `âœ… ✅ SMOKE OK | files=20 | parity=ALL_TRUE | integrity_errors=0`
  Red shows:
  - `âŒ Parity failure â€” see integrity artifacts`
- Triage: open uploaded `INTEGRITY_REPORT.json` and `build.json` for `parity` and `parity_deltas`.
  - Fix the source pack with mismatched key(s), re-run locally (`make smoke`), then push.

## Golden Snapshot

- Purpose: lock deterministic output for a canonical v3 intake and fail CI on drift.
- Fixture: `fixtures/intake_v3_golden.json` (minimal-but-complete v3).
- Snapshot: `fixtures/expected_pack_golden/01..20_*.json` generated from the fixture.
- Test: `tests/integ_py/test_golden_snapshot.py` builds from the fixture, asserts:
  - 20 canonical files exist
  - integrity errors == 0; parity ALL_TRUE (02/11/03/17 vs 14)
  - byte-for-byte equality vs snapshot (normalized to `\n` line endings)
- CI: runs the golden snapshot test (blocking) and uploads `_artifacts/golden-diff/**` on mismatch.


## Overlays (optional)

You can auto-apply overlays immediately after a successful `/build`:

- Feature flag: set `NEO_APPLY_OVERLAYS=true` to enable.
- Config: `overlays/config.yaml`
  - `apply`: list of overlays to run (order matters)
    - `19_SME_Domain` â€” ensures pack 19 refs align to sector/region/regulators
    - `20_Enterprise` â€” ensures brand/legal/stakeholders presence
    - `persistence_adaptiveness` â€” applies operations from `overlays/apply.persistence_adaptiveness.yaml`

Safety and integrity:
- The applier performs additive, minimal diffs; required keys are not overwritten.
- After apply, integrity and KPI parity (02/03/11/14/17) are recomputed. If any check fails, changes are rolled back.
- Response includes `overlays_applied: true/false` and an `overlay_summary` with `applied`, `touched_packs`, `deltas`, and post-apply `parity`.

## Build & Verify Panel

- Save Profile â†’ click Build Repo to POST `/build` and write the 20 canonical files.
- Status cards show:
  - Parity: 02â†”14 and 11â†”02 with checkmarks.
  - Integrity: file_count, errors, warnings (expandable).
  - Output path: copyable filesystem path to the generated repo.
  - Health chip: GET `/health` to display app_version, pid, and repo_output_dir.

## Reviewing Builds in the UI

- Last-Build banner: on load the UI fetches `/last-build` and displays the most recent build with timestamp, output path, aggregate parity badge, and whether overlays were applied.
- Download ZIP: after a build completes or from the Last-Build banner, click â€œDownload ZIPâ€ or fetch via `GET /download/zip` to retrieve the zipped 20-pack.
- Parity-deltas tooltips: when any parity check is false, an info icon appears next to the parity card. Activate it (click or keyboard) to see the exact key deltas, e.g. `03 PRI_min â€” 0.940 â†’ 0.950`.



## License

Project NEO Agent is released under the MIT License. See `LICENSE` for details.


### Overlay summary

When overlays are applied during a build (feature flag `NEO_APPLY_OVERLAYS=true`), the server persists an extended `_last_build.json` that includes `overlay_summary`:

- `applied`: boolean, whether overlays ran and were retained (not rolled back).
- `items[]`: Name, Version, Status, Allowlisted, Notes for each applied overlay action.
- `rollback`: `{ supported: true, last_action: 'none'|'rollback', ts: 'ISO8601' }`.

In the UI, a â€œView overlaysâ€ button appears on the Last-Build banner when `items.length > 0`. Clicking opens an accessible modal (keyboard/ESC/focus-trap) with a table of overlay items and a â€œCopy overlay JSONâ€ action. `/last-build` response headers remain strict: `Cache-Control: no-store`, `X-NEO-Intake-Version: v3.0`.


### Run the intake app locally

To launch the intake form from a terminal on Windows, macOS, or Linux:

1. Install dependencies: ``pip install -e .[dev]``
2. Start the server (PowerShell or VS Code terminal): ``neo-agent serve --host 127.0.0.1 --port 5000``
3. Open http://127.0.0.1:5000/ in your browser. The server logs the health check and profile output paths.

Alternative entry points are also available if you prefer invoking Python directly:

- ``python -m neo_agent.intake_app``
- ``python -c "from neo_agent.intake_app import create_app; create_app().serve(host='127.0.0.1', port=5000)"``

Both commands respect the ``HOST`` and ``PORT`` environment variables, allowing you to override the bind address without changing code.

A quick smoke check after startup:

- ``curl http://127.0.0.1:5000/`` should return the intake HTML.
- ``curl http://127.0.0.1:5000/api/profile/validate -X POST -H "Content-Type: application/json" -d '{}'`` returns JSON containing ``status`` and ``issues`` fields.

## Docker Quickstart

- Build image: ``docker build -t neo-intake:local --build-arg GIT_SHA=$(git rev-parse --short HEAD) .``
- Run: ``docker run -p 5000:5000 --env-file .env neo-intake:local``
- Health: ``curl -i http://127.0.0.1:5000/health`` â†’ 200, headers include `X-NEO-Intake-Version` and `X-Commit-SHA`.

### Compose (dev)

Use ``docker-compose.dev.yml`` for local iteration:

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up --build
```

The service listens on ``http://127.0.0.1:5000`` and emits structured JSON logs to stdout.

### Headers you'll see

- `X-Request-ID` â€” echoed from client or generated per request.
- `X-Response-Time-ms` â€” integer processing time for the request.

Error envelope example (uniform for 400/404/405/413/429/500):

```json
{"status":"error","code":"NOT_FOUND","message":"Not Found","details":{},"req_id":"..."}
```

## Legacy payloads

- Behavior matrix:
  - Legacy-only payload (top-level ``legacy`` present, no v3 concept keys ``context``/``role``/``governance_eval``) â†’ auto-migrated to v3 before validation and saved if required v3 fields are satisfied.
  - Mixed legacy+v3 for the same concept â†’ rejected with code ``DUPLICATE_LEGACY_V3_CONFLICT`` and per-field paths; telemetry is emitted with ``{"legacy_detected": true, "conflicts": <n>}``.
  - Pure v3 payload â†’ validated and saved as-is.

### Error codes

- ``DUPLICATE_LEGACY_V3_CONFLICT``: legacy fields coexist with v3 fields for the same concept.
  - Example shape:
    ```json
    {
      "status": "invalid",
      "code": "DUPLICATE_LEGACY_V3_CONFLICT",
      "conflicts": [
        {
          "code": "DUPLICATE_LEGACY_V3_CONFLICT",
          "legacy_path": "legacy.traits",
          "v3_path": "persona",
          "hint": "Remove legacy fields or provide legacy-only payload for auto-migration."
        }
      ]
    }
    ```

### Legacy â†’ v3 mapping

- legacy.sector â†’ sector_profile.sector
- legacy.role â†’ role.role_code
- legacy.regulators[] â†’ sector_profile.regulatory[]
- legacy.traits[] / legacy.attributes[] â†’ persona.traits[]
- legacy.voice â†’ brand.voice.voice_traits[]
- legacy.tools[] / legacy.capabilities[] â†’ capabilities_tools.tool_suggestions[]
- legacy.human_gate.actions[] â†’ capabilities_tools.human_gate.actions[]
- legacy.memory.scopes[] â†’ memory.memory_scopes[]
- legacy.memory.packs[] â†’ memory.initial_memory_packs[]
- legacy.memory.sources[] â†’ memory.data_sources[]
- legacy.kpi.PRI_min â†’ governance_eval.gates.PRI_min
- legacy.kpi.HAL_max â†’ governance_eval.gates.hallucination_max
- legacy.kpi.AUD_min â†’ governance_eval.gates.audit_min

Diagnostics example (unknowns are dropped):

```json
{
  "dropped": ["legacy.unknown_field"],
  "mappings_applied": [
    "legacy.roleâ†’role.role_code",
    "legacy.kpi.PRI_minâ†’governance_eval.gates.PRI_min"
  ]
}
```

## Operational Checklists

- Release checklist: see RELEASE_CHECKLIST.md
- Hotfix template: see HOTFIX_TEMPLATE.md
\n### CI Status (main)
\n+[![CI (Unit + Integ/Smoke)](https://github.com/THESPRYGUY/Project_agent_NEO/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/THESPRYGUY/Project_agent_NEO/actions/workflows/ci.yml)
\n+CI filter note (v2.1.2): Added `feat/**` and `hotfix/**` to workflow push filters; `pull_request` remains on `main` (types: opened, synchronize, reopened). Job names unchanged for Branch Protection.
\n### How KPI report is generated
\n1. Run `python scripts/gen_kpi_report.py --root generated_repos/agent-build-007-2-1-1 --out reports/`.
\n2. The script reads packs 02, 11, 14, and 15 to gather KPI targets and gates.
\n3. PRI, HAL, and AUD fall back to target thresholds when live CI data is missing.
\n4. Outputs land in `reports/kpi_report.json` plus `reports/kpi_report.md`.
\n5. Telemetry emits `kpi_report_generated` for observability ingestion.
\n6. Use `--ci` to print a terse summary in workflow logs.
\n7. Workflow `kpi-report-smoke` publishes the artifact for review.
