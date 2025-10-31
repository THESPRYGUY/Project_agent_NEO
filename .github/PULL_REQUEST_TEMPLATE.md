## Summary

Explain the change and its scope. Link to docs where applicable.

## Checklist
- [ ] Single feature set; scoped PR
- [ ] Parity unchanged (strict parity ON); golden snapshot unaffected
- [ ] Required CI jobs green (unit-python, unit-js, golden snapshot, docker-build-smoke, smoke)
- [ ] If applicable, SCA artifacts uploaded (warn-only): `sca-pip-audit.json`, `sca-npm-audit.json`
- [ ] Single-line smoke summary present (exactly one line) â€” either  
      `âœ… SMOKE OK | files=20 | parity=ALL_TRUE | integrity_errors=0`  
      or the failure variant; CI artifact links included

## Notes
- Artifacts link(s):
- Docs link(s):

## Build-Path Gates (required when touching builder/SoT paths)
- [ ] Paste the validator line: ✅ contract-validate: OK (hash=<HASH>)
- [ ] ZIP sha256 parity proof (default vs ?outdir=) included (hashes identical)
- [ ] Statement confirming “no .tmp residue” test present for failure paths
- [ ] Lock behavior verified if builder touched (423 + Retry-After header = 5)