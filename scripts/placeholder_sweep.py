#!/usr/bin/env python3
"""Placeholder sweep for generated repos.

Runs the existing repo_audit scanner and fails fast when placeholder findings
are detected. Outputs a concise summary to stdout for CI visibility.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from repo_audit import run_audit, Finding  # type: ignore


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail fast when placeholder tokens remain in generated packs")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1] / "generated_repos"),
        help="Root directory containing generated agent repos",
    )
    parser.add_argument(
        "--project",
        default="agent-build-007-2-1-1",
        help="Specific project folder to scan relative to --root (default: agent-build-007-2-1-1)",
    )
    parser.add_argument(
        "--formats",
        default="",
        help="Optional comma-delimited formats for repo_audit reports (default: none)",
    )
    return parser.parse_args(argv)


def _summary(findings: Sequence[Finding]) -> str:
    lines = ["Placeholder findings detected:"]
    for finding in sorted(findings, key=lambda f: (f.project, Path(f.file).name, f.key_path)):
        lines.append(
            f"- [{finding.severity}] {finding.project}/{Path(finding.file).name} :: {finding.key_path} -> {finding.value_snippet}"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    ns = _parse_args(argv or sys.argv[1:])
    root = Path(ns.root)
    target = root / ns.project
    if not target.exists():
        print(f"placeholder_sweep: target directory not found ({target}); skipping", file=sys.stderr)
        return 0

    formats = [fmt.strip() for fmt in (ns.formats or "").split(",") if fmt.strip()]
    findings = run_audit(target, formats=formats or ())
    placeholder_findings = []
    for finding in findings:
        path = Path(finding.file)
        if finding.issue_type != "placeholder":
            continue
        if path.suffix.lower() != ".json":
            continue
        parts = {p.lower() for p in path.parts}
        if "reports" in parts or "docs" in parts:
            continue
        placeholder_findings.append(finding)

    if placeholder_findings:
        print(_summary(placeholder_findings), file=sys.stderr)
        return 2

    print(f"placeholder_sweep: OK — no placeholder findings in {target}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
