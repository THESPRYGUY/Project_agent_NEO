# Contributing
## Branch Protection Policy (Solo Maintainer)
- Pull requests: required (for history), approvals: **0**.
- Required checks on `main`: schema-validate, intake-mapper-guard, placeholder-sweep, repo-audit, unit-python, unit-js, ui-schema-smoke, registry-consistency, governance-crosscheck.
- Admins enforced; conversations must be resolved; no force-pushes to `main`.
- Rationale: solo maintainer; CI acts as the gate. For temporary emergencies, create a hotfix branch; PR still required.