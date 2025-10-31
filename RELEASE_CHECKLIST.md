# Release Checklist

Use this checklist for each release before tagging and publishing.

- Contract validator: paste single‑line `✅ contract-validate: OK (hash=<HASH>)`
- ZIP parity proof: sha256(default) == sha256(`?outdir=<last-build outdir>`)
- No `.tmp` residue: confirm `_generated/<AGENT_ID>/.tmp` empty after failures
- Lock behavior: 423 + `Retry-After: 5` present when concurrent /build occurs
- Guard pass: “Shim Redirect Guard” status check green (no shim hits)
- SLOs pass: build.duration_ms p95 < 1500ms; zip_bytes p95 < 50MB
- Artifacts attached: repo.zip, INTEGRITY_REPORT.json, build.json
- Notes include highlights + retro snapshot

## Commands

- Tag and release: `make release VERSION=x.y.z`
- Verify validator: `python scripts/contract_validate.py <pack_dir>`
