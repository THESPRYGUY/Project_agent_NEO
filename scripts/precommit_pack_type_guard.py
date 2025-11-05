#!/usr/bin/env python
"""Pre-commit hook that ensures pack JSON files have expected container types."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, Tuple, Type

PACK_EXPECTATIONS: Dict[str, Iterable[Tuple[str, Type[object]]]] = {
    "12_Tool+Data-Registry_v2.json": (
        ("connectors", list),
        ("data_sources", list),
        ("datasets", list),
    ),
    "14_KPI+Evaluation-Framework_v2.json": (("kpis", list), ("gates", dict)),
    "15_Observability+Telemetry_Spec_v2.json": (("events", list), ("dashboards", dict)),
    "17_Lifecycle-Pack_v2.json": (("go_live", dict), ("rollback", dict)),
}

PACK_PATTERN = re.compile(r"(?P<name>\d{2}_.+\.json)$")


def validate_file(path: Path) -> Iterable[str]:
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        yield f"{path}: invalid JSON ({exc})"
        return
    if not isinstance(payload, dict):
        yield f"{path}: top-level must be an object, not {type(payload).__name__}"
        return

    match = PACK_PATTERN.search(path.as_posix())
    if not match:
        return

    filename = match.group("name")
    expectations = PACK_EXPECTATIONS.get(filename, ())
    for key, expected_type in expectations:
        value = payload.get(key)
        if value is None:
            continue
        if not isinstance(value, expected_type):
            yield (
                f"{path}: field '{key}' expected {expected_type.__name__}, "
                f"found {type(value).__name__}"
            )


def main(argv: Iterable[str]) -> int:
    errors = []
    for arg in argv:
        path = Path(arg)
        if not path.exists() or path.suffix.lower() != ".json":
            continue
        errors.extend(validate_file(path))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
