# Security Policy

This project values the security and privacy of users and operators. The following policy describes supported versions, how to report vulnerabilities, our disclosure process, and resolution timelines.

## Supported Versions
- Application runtime: Python 3.11 (CI standard), Node.js 20.x for UI tests
- Container: Image built from `Dockerfile` in CI, tagged per release
- Only the latest `main` and the most recent tagged release receive security updates

## Reporting a Vulnerability
- Preferred: Open a private GitHub Security Advisory for this repository
- Alternative: Contact repository maintainers via the GitHub “Security” tab
- Please include reproduction steps, affected components, and any impact assessment

## Disclosure Policy
- We follow responsible disclosure. Please do not open a public issue for security findings
- We will coordinate a fix and acknowledge reporters if desired

## Severity and SLAs (Target)
- Critical (RCE, auth bypass, credential leak): triage within 24h, patch within 7 days
- High (privilege escalation, data exfil paths): triage within 2 business days, patch within 14 days
- Medium (DoS, info disclosure without PII/secret exposure): triage within 5 business days, patch in next sprint
- Low (best practices, hardening): triage within 10 business days, scheduled as capacity permits

## Dependency Security
- Python: pinned constraints in `constraints/requirements.lock` (and dev in `constraints/requirements-dev.lock`)
- Node: `package-lock.json` is authoritative; CI uses `npm ci`
- CI runs Software Composition Analysis (SCA) as warn-only; reports are uploaded as artifacts on every PR/Push

## Telemetry & Privacy
- Logs must not contain secrets or PII. Redact or hash where applicable
- Reasoning artifacts must not include raw chain-of-thought; only sanitized summaries are permitted

