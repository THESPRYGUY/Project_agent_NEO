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

