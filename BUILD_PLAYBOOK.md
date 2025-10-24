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

