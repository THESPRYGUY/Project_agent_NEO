#!/usr/bin/env python3
"""Parse SCA artifacts and print a concise summary.

Outputs a single line suitable for CI logs and PR body:
  SCA Summary — pip_audit: critical=X, high=Y; npm_audit: critical=A, high=B

This script never exits non-zero; it is warn-only.
"""
from __future__ import annotations

import json
from pathlib import Path


def _safe_load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def count_pip_audit_crit_high(obj) -> tuple[int, int]:
    # pip-audit JSON may be a dict with "dependencies" or a list of deps
    deps = []
    if isinstance(obj, dict) and isinstance(obj.get("dependencies"), list):
        deps = obj.get("dependencies")
    elif isinstance(obj, list):
        deps = obj
    critical = 0
    high = 0
    for dep in deps or []:
        for v in (dep or {}).get("vulns", []) or []:
            sev = str((v or {}).get("severity") or "").upper()
            if sev == "CRITICAL":
                critical += 1
            elif sev == "HIGH":
                high += 1
    return critical, high


def count_npm_audit_crit_high(obj) -> tuple[int, int]:
    # Prefer metadata.vulnerabilities if present (npm v8+)
    try:
        meta = (obj or {}).get("metadata", {})
        vmap = meta.get("vulnerabilities", {})
        if isinstance(vmap, dict):
            c = int(vmap.get("critical") or 0)
            h = int(vmap.get("high") or 0)
            return c, h
    except Exception:
        pass
    # Fallback: iterate vulnerabilities map
    critical = 0
    high = 0
    try:
        vulns = (obj or {}).get("vulnerabilities", {})
        if isinstance(vulns, dict):
            for _, entry in vulns.items():
                sev = str((entry or {}).get("severity") or "").upper()
                if sev == "CRITICAL":
                    critical += 1
                elif sev == "HIGH":
                    high += 1
    except Exception:
        pass
    return critical, high


def main() -> int:
    root = Path.cwd()
    pip_path = root / "sca-pip-audit.json"
    npm_path = root / "sca-npm-audit.json"
    pip_obj = _safe_load(pip_path) if pip_path.exists() else None
    npm_obj = _safe_load(npm_path) if npm_path.exists() else None
    pip_c, pip_h = count_pip_audit_crit_high(pip_obj) if pip_obj is not None else (0, 0)
    npm_c, npm_h = count_npm_audit_crit_high(npm_obj) if npm_obj is not None else (0, 0)
    print(
        f"SCA Summary — pip_audit: critical={pip_c}, high={pip_h}; npm_audit: critical={npm_c}, high={npm_h}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

