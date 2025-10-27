# Project NEO Agent

Project NEO Agent provides a lightweight, test-driven scaffold for experimenting with
agentic workflows. The repository intentionally limits itself to twenty files while
still covering configuration, planning, execution, and telemetry capabilities.

## Features

- **Deterministic configuration** – dataclass based models with JSON helpers keep
  runtime settings predictable.
- **Conversation aware state** – a structured conversation history is maintained for
  every dispatch, enabling downstream analysis.
- **Modular skills** – skills are simple callables that can be dynamically discovered
  from configuration entrypoints.
- **Planning pipeline** – the runtime produces a basic plan and executes each step
  through a configurable pipeline.
- **Observability** – event emission and telemetry utilities capture metrics during
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
creates `agent_profile.json` alongside a `generated_specs/` directory containing the
derived configuration and metadata artifacts used by the generator.

#### Intake Section Order & Gating
- Order: Agent Profile → Business Context (NAICS + Domain) → Business Function & Role → Persona Alignment → Toolsets → Attributes → Preferences → LinkedIn → Custom Notes
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
- `repo.zip` — zipped generated repo
- `INTEGRITY_REPORT.json` — integrity + parity summary
- `build.json` — CI-parsed summary with `file_count`, `parity`, `integrity_errors`

The command prints a one-line status, for example:

```
SMOKE OK | files=20 | parity=ALL_TRUE | integrity_errors=0
```

### Strict Parity in CI

- Gate: CI enforces KPI parity as a hard gate with `FAIL_ON_PARITY=true` across all jobs.
- Artifacts: job uploads `_artifacts/**`, `**/INTEGRITY_REPORT.json`, `**/build.json`, and any `**/*.zip` on every run (pass/fail).
- PR Summary: CI posts a one-line outcome. Green shows:
  - `✅ SMOKE OK | files=20 | parity=ALL_TRUE | integrity_errors=0`
  Red shows:
  - `❌ Parity failure — see integrity artifacts`
- Triage: open uploaded `INTEGRITY_REPORT.json` and `build.json` for `parity` and `parity_deltas`.
  - Fix the source pack with mismatched key(s), re-run locally (`make smoke`), then push.

## Overlays (optional)

You can auto-apply overlays immediately after a successful `/build`:

- Feature flag: set `NEO_APPLY_OVERLAYS=true` to enable.
- Config: `overlays/config.yaml`
  - `apply`: list of overlays to run (order matters)
    - `19_SME_Domain` — ensures pack 19 refs align to sector/region/regulators
    - `20_Enterprise` — ensures brand/legal/stakeholders presence
    - `persistence_adaptiveness` — applies operations from `overlays/apply.persistence_adaptiveness.yaml`

Safety and integrity:
- The applier performs additive, minimal diffs; required keys are not overwritten.
- After apply, integrity and KPI parity (02/03/11/14/17) are recomputed. If any check fails, changes are rolled back.
- Response includes `overlays_applied: true/false` and an `overlay_summary` with `applied`, `touched_packs`, `deltas`, and post-apply `parity`.

## Build & Verify Panel

- Save Profile → click Build Repo to POST `/build` and write the 20 canonical files.
- Status cards show:
  - Parity: 02↔14 and 11↔02 with checkmarks.
  - Integrity: file_count, errors, warnings (expandable).
  - Output path: copyable filesystem path to the generated repo.
  - Health chip: GET `/health` to display app_version, pid, and repo_output_dir.

## Reviewing Builds in the UI

- Last-Build banner: on load the UI fetches `/last-build` and displays the most recent build with timestamp, output path, aggregate parity badge, and whether overlays were applied.
- Download ZIP: after a build completes or from the Last-Build banner, click “Download ZIP” to retrieve a zipped copy of the repo via `/build/zip?outdir=<path>`.
- Parity-deltas tooltips: when any parity check is false, an info icon appears next to the parity card. Activate it (click or keyboard) to see the exact key deltas, e.g. `03 PRI_min — 0.940 → 0.950`.



## License

Project NEO Agent is released under the MIT License. See `LICENSE` for details.


### Overlay summary

When overlays are applied during a build (feature flag `NEO_APPLY_OVERLAYS=true`), the server persists an extended `_last_build.json` that includes `overlay_summary`:

- `applied`: boolean, whether overlays ran and were retained (not rolled back).
- `items[]`: Name, Version, Status, Allowlisted, Notes for each applied overlay action.
- `rollback`: `{ supported: true, last_action: 'none'|'rollback', ts: 'ISO8601' }`.

In the UI, a “View overlays” button appears on the Last-Build banner when `items.length > 0`. Clicking opens an accessible modal (keyboard/ESC/focus-trap) with a table of overlay items and a “Copy overlay JSON” action. `/last-build` response headers remain strict: `Cache-Control: no-store`, `X-NEO-Intake-Version: v3.0`.


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
