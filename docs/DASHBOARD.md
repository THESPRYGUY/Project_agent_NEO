# CI Telemetry Dashboard (Seed)

This file describes how to explore CI telemetry artifacts until Grafana/Prometheus are wired.

- Artifact: `telemetry.jsonl` (uploaded by the `smoke` job).
- Events:
  - `build:start`, `build:success`, `build:error`
  - `zip_download`, `redirect.generated_specs.hit`
  - Aggregates per run: `run_aggregates` with fields
    - `build_duration_ms_p50`, `build_duration_ms_p95`
    - `zip_bytes_p50`, `zip_bytes_p95`

## Quick recipes (jq)

- Count legacy shim hits per run:
  jq -r 'select(.event=="redirect.generated_specs.hit") | .event' telemetry.jsonl | wc -l

- Extract per-run aggregates:
  jq -r 'select(.event=="run_aggregates")' telemetry.jsonl

- Summarize build durations across runs (paste multiple artifacts):
  cat */telemetry.jsonl | jq -r 'select(.event=="run_aggregates") | [.build_duration_ms_p50, .build_duration_ms_p95] | @tsv'

- Track zip size percentiles (bytes):
  cat telemetry.jsonl | jq -r 'select(.event=="run_aggregates") | [.zip_bytes_p50, .zip_bytes_p95] | @tsv'

Notes:
- SLOs (warn-only for now): p95 build.duration_ms < 1500; p95 zip_bytes < 50MB.
- When external metrics are live, mirror these aggregates and add alerts in the dashboard.
