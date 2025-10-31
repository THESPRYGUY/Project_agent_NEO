# Hotfix Template

Use this template for hotfix PRs and release notes.

## Summary
- Issue and impact
- Scope of fix

## Validation
- [ ] Unit tests updated/added
- [ ] Contract validator ✅ line pasted
- [ ] ZIP parity proof (default vs `?outdir=`)
- [ ] No `.tmp` residue on failure paths
- [ ] Lock behavior unaffected (423 + Retry-After=5)
- [ ] Guard pass (Shim Redirect Guard)
- [ ] SLOs pass (build.duration_ms p95 < 1500; zip_bytes p95 < 50MB)

## Risk
- Rollback plan
- Follow-up tasks
