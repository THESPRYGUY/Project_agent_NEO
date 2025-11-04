#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from mapper import apply_intake, IntakeValidationError


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply an intake payload to generated pack files."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to intake JSON payload conforming to intake_contract_v1.json.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("generated_repos") / "agent-build-007-2-1-1",
        help="Path to the build root containing canonical pack files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze and report mapping/diff without writing pack files.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional path to write mapping/diff report JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.input.exists():
        print(f"ERROR: intake payload not found: {args.input}", file=sys.stderr)
        return 2

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in intake payload ({exc})", file=sys.stderr)
        return 2

    try:
        result = apply_intake(payload, args.root, dry_run=args.dry_run)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except IntakeValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: failed to apply intake: {exc}", file=sys.stderr)
        return 1

    result["build_root"] = str(args.root.resolve())
    result["generated_at"] = datetime.now(timezone.utc).isoformat()

    output = json.dumps(result, indent=2, sort_keys=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
