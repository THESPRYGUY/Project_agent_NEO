# Project NEO v2.1.1 — Release Assurance Pack

Validator
- ✅ contract-validate: OK (hash=ab2809b8fc7fd167fec0390e4b1c1677b90864a5b6d0ab5f911e687e156e7f95)

_last_build.json (v2.1.1 keys)
- schema_version, agent_id, outdir, files, ts, zip_hash

ZIP parity (sha256)
- default: 64f6fc916cd25351a533c00de3d0623566d09569c2fb1db89ebe17ccccea4342
- ?outdir=: 64f6fc916cd25351a533c00de3d0623566d09569c2fb1db89ebe17ccccea4342

SLO snapshot (thresholds: p95 < 1500ms; p95 < 50MB)
- build.duration_ms: p50≈370ms, p95≈370ms
- zip_bytes: p50≈14KB, p95≈14KB

Shim Redirect Guard
- telemetry.jsonl artifact present in CI
- redirect.generated_specs.hit = 0 (guard job passes; fails on any hits)

Telemetry jq
- jq -r 'select(.event=="run_aggregates")' telemetry.jsonl
