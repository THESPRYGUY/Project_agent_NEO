# Build Playbook — Quick Triage

Use this checklist to triage builds quickly and deterministically.

- Check Last Build: open the intake UI; confirm the Last-Build banner appears with the expected timestamp and output path.
- Aggregate Parity: if the badge shows NEEDS REVIEW, open the info icon(s) on the parity card to view deltas.
  - Example: `03 PRI_min — 0.940 → 0.950` means 03 activation is below the 02/14 target.
- Re-run Smoke: if parity flipped or deltas exist, re-run the smoke to validate determinism: `make smoke`.
- Download ZIP: use the “Download ZIP” button to capture the generated repo and attach it to your review.

Endpoints used:
- `GET /last-build` — compact JSON summary of the last build.
- `GET /build/zip?outdir=<path>` — secure download of the built repo as a zip; requires `outdir` to be a subpath of `NEO_REPO_OUTDIR`.


Overlay summary triage:
- When NEO_APPLY_OVERLAYS=true, the server persists overlay_summary in _last_build.json.
- From the Last-Build banner, click "View overlays" to inspect the table (Name, Version, Status, Allowlisted, Notes).
- If a build fails parity, validate allowlist/status/notes in the overlay modal, then re-run smoke or rollback as needed.

## PR Gates

- Required: unit-python (pytest, coverage >= 85%) and unit-js (vitest thresholds).
- Advisory: integration tests via `pytest -m integ` (non-blocking).
- Required: smoke (`python ci/smoke.py`) builds the 20-pack and validates parity/integrity.

## Strict Parity in CI

- Configuration: `FAIL_ON_PARITY=true` is set for all CI jobs.
- Behavior: the smoke step exits nonzero when parity is false and posts a concise summary to the PR.
- Artifacts (always uploaded):
  - `_artifacts/**` (includes `smoke.log`)
  - `**/INTEGRITY_REPORT.json`, `**/build.json`, `**/*.zip`
- Interpreting PR Summary:
  - `✅ SMOKE OK | files=20 | parity=ALL_TRUE | integrity_errors=0` → proceed.
  - `❌ Parity failure — see integrity artifacts` → open uploaded `INTEGRITY_REPORT.json` and `build.json` → inspect `parity_deltas`.
- Triage Deltas:
  - Look for lines like `- 14:PRI_min got=0.94 expected=0.95`.
  - Update the mismatched pack or intake source; re-run `make smoke`.

## How to re-baseline intentionally

When deterministic outputs change by design, re-baseline the golden snapshot:

1) Run the re-baseline helper locally

```bash
python scripts/make_golden.py
```

This rebuilds the golden repo from `fixtures/intake_v3_golden.json` and overwrites
`fixtures/expected_pack_golden/*`. It prints “GOLDEN UPDATED” and lists changed files.

2) Commit and open a PR

- Commit message should include: `INTENTIONAL SNAPSHOT UPDATE`.
- In the PR description, explain the change rationale (why the canonical output changed).
- CI will pass if the snapshot matches and parity/integrity gates hold.

3) On CI failures

- Inspect uploaded `_artifacts/golden-diff/**` for unified diffs of the first drifts.
- Correct the source or re-run the helper if the change is expected.


## Legacy payload triage

- New guard rejects mixed legacy+v3 payloads at `/save` with `DUPLICATE_LEGACY_V3_CONFLICT`.
- Action: remove legacy fields or submit a legacy-only payload to auto-migrate.
- Example conflict object:
  ```json
  {
    "code": "DUPLICATE_LEGACY_V3_CONFLICT",
    "legacy_path": "legacy.kpi",
    "v3_path": "governance_eval.gates",
    "hint": "Remove legacy fields or provide legacy-only payload for auto-migration."
  }
  ```
