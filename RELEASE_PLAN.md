# Release Plan — v2.1.2

Scope
1) Remove 307 shim (keep guard until hits=0 for 24h)
2) External metrics sink + dashboard v1 (Grafana/Prometheus)
3) NFS lock semantics note/test (FileLock on NFS)
4) Windows long-path exploration (guarded determinism)

Owners & Targets
- #54 Remove 307 shim — Owner: @THESPRYGUY — Target: 2025-11-14
- #57 External metrics sink — Owner: @THESPRYGUY — Target: 2025-11-30
- #58 NFS lock semantics — Owner: @THESPRYGUY — Target: 2025-11-21
- #59 Windows long-paths — Owner: @THESPRYGUY — Target: 2025-11-30
- #60 Dashboard v1 — Owner: @THESPRYGUY — Target: 2025-11-30

Changelog (CI notes)
- Added eat/** and hotfix/** to workflow push filters; pull_request unchanged (main only; types: opened, synchronize, reopened). Job names preserved for Branch Protection.

