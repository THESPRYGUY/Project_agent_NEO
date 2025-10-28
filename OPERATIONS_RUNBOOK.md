# Operations Runbook — Project NEO Intake Service

- Environments: local (compose), staging, prod
- Runtime: Python 3.11, gunicorn, WSGI app `wsgi:app`

## Environment Variables
- `NEO_REPO_OUTDIR` — base path for generated repos (default: `<repo>/_generated`)
- `FAIL_ON_PARITY` — hard‑fail KPI parity in integrity checks (`true|false`)
- `NEO_APPLY_OVERLAYS` — apply overlays post build (`true|false`)
- `LOG_LEVEL` — logging level (`DEBUG|INFO|WARNING|ERROR`)
- `GIT_SHA` — injected at build time for headers (`X-Commit-SHA`)

## Health & Headers
- `GET /health` → 200 JSON: `{status, build_tag, app_version, pid, repo_output_dir, ...}`
- Response headers include:
  - `X-NEO-Intake-Version: v3.0`
  - `X-Commit-SHA: <sha>`
  - `Cache-Control: no-store, must-revalidate`

## Logs
- Structured JSON to stdout: `{ts, level, logger, msg, [event], [payload]}`
- Tune via `LOG_LEVEL`.

## Docker
- Build: `docker build -t neo-intake:local --build-arg GIT_SHA=$(git rev-parse --short HEAD) .`
- Run: `docker run -p 5000:5000 --env-file .env neo-intake:local`
- Health: `curl -i http://localhost:5000/health`

## Compose (dev)
- `docker compose -f docker-compose.dev.yml up --build`
- Mounts repo, exposes `:5000`.

## Release
- Tag `v*` → GH workflow builds image, smoke‑tests `/health`, generates artifacts:
  - `repo.zip` (source archive)
  - `INTEGRITY_REPORT.json` (from builder)
  - `build.json` (tag, sha, timestamp)
- Release attaches artifacts to the tag.


## Resilience & Limits

Environment variables (override via `.env` or container env):

- `MAX_BODY_BYTES` (default `1048576`) – hard cap on request body size. Exceeding returns `413` with a JSON error envelope. Keep at 1–5MB for typical form/JSON posts.
- `RATE_LIMIT_RPS` (default `5`) – per‑IP token refill rate in requests per second.
- `RATE_LIMIT_BURST` (default `10`) – per‑IP burst tokens. Set both to `0` to disable non‑exempt traffic (useful in maintenance).
- `TELEMETRY_SAMPLE_RATE` (default `0.1`) – sampling rate (0.0–1.0) for non‑critical telemetry. Errors always emit.

Headers emitted on middleware‑wrapped responses:
- `X-Request-ID` – echoed from client `X-Request-ID` or generated.
- `X-Response-Time-ms` – integer duration from request receive to response.

Error envelope (uniform across 400/404/405/413/429/500):

```json
{"status":"error","code":"<UPPER_SNAKE>","message":"...","details":{},"req_id":"..."}
```

Rate‑limit exemptions: `GET /health`, `GET /last-build`.

## Security

Environment variables (auth stub is optional and OFF by default):

- `AUTH_REQUIRED` (default `false`) — when `true`, all non-`/health` routes require a valid Bearer token
- `AUTH_TOKENS` (default empty) — comma‑separated list of accepted tokens

Behavior:
- When `AUTH_REQUIRED=true` and the `Authorization: Bearer <token>` header is missing/invalid, responses return `401` with a JSON envelope `{status:"error", code:"UNAUTHORIZED", ...}` and `WWW-Authenticate: Bearer` header
- `/health` is always exempt to support liveness/readiness probes

Headers & Privacy:
- Always emit: `X-Request-ID`, `X-Response-Time-ms`, `Cache-Control: no-store`
- Do not log secrets, tokens, or PII. Ensure any identifiers are hashed or redacted

Dependency Pinning Policy:
- Python: pins live in `constraints/requirements.lock` and `constraints/requirements-dev.lock`; update monthly or on CVE
- Node: `package-lock.json` is authoritative; update monthly or on CVE via `npm audit fix` PRs

SCA Overview (warn‑only):
- CI runs `pip-audit` for Python and `npm audit --production` for Node
- Findings do not fail PRs; reports are uploaded as artifacts for review
