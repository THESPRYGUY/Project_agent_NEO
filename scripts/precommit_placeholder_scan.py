#!/usr/bin/env python
"""Pre-commit hook to block placeholder tokens such as TODO or FIXME."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

PATTERN = re.compile(r"\b(TODO|FIXME|@@PLACEHOLDER@@)\b")
SKIP_DIRS = {"generated_repos", "node_modules", ".git", "scripts", "neo_build", "_backup"}
SKIP_FILES = {"scripts/compare_gen2_vs_generated.py"}


def scan_file(path: Path) -> Iterable[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        yield f"{path}: unable to read file ({exc})"
        return
    matches = list(PATTERN.finditer(text))
    for match in matches:
        line_no = text[: match.start()].count("\n") + 1
        yield f"{path}:{line_no}: found placeholder token '{match.group(0)}'"


def main(args: Iterable[str]) -> int:
    violations = []
    for arg in args:
        path = Path(arg)
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        rel = path.as_posix()
        if rel in SKIP_FILES:
            continue
        violations.extend(scan_file(path))
    if violations:
        for violation in violations:
            print(violation, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
