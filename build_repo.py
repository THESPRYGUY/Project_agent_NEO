"""CLI for building deterministic 20-pack NEO agent repositories.

Usage:
  python build_repo.py --intake agent_profile.json --out ./generated_repos --extend --verbose [--strict] [--force-utf8] [--emit-parity]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Mapping

from neo_build.contracts import CANONICAL_PACK_FILENAMES, KPI_TARGETS
from neo_build.utils import FileLock, json_write, slugify
from neo_build.writers import write_repo_files
from neo_build.validators import attach_integrity_to_reporting_pack, integrity_report


def _load_json(path: Path, *, force_utf8: bool) -> Mapping[str, Any]:
    data: bytes
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        if not force_utf8:
            raise
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        return json.loads(text)


def build_repo(intake_path: Path, out_dir: Path, *, extend: bool, strict: bool, verbose: bool, force_utf8: bool, emit_parity: bool) -> int:
    if not intake_path.exists():
        print(f"ERROR: intake file not found: {intake_path}", file=sys.stderr)
        return 2
    profile = _load_json(intake_path, force_utf8=force_utf8)
    agent = profile.get("agent", {}) if isinstance(profile, Mapping) else {}
    identity = profile.get("identity", {}) if isinstance(profile, Mapping) else {}
    name = (identity.get("agent_id") or agent.get("name") or "agent").strip()
    version = (agent.get("version") or "").strip()
    slug_source = "-".join([s for s in [name, version] if s])
    slug = slugify(slug_source) or slugify(name) or "agent"

    base = out_dir.resolve()
    base.mkdir(parents=True, exist_ok=True)
    target = base / slug
    target.mkdir(parents=True, exist_ok=True)

    snapshots_dir = Path.cwd() / "snapshots" / slug
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshots_dir / "snapshot.json"
    json_write(snapshot_path, profile)  # snapshot lock source data

    lock = FileLock(snapshots_dir / "build.lock")
    try:
        lock.acquire()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    try:
        packs = write_repo_files(profile, target)
        # Optional parity artifacts
        if emit_parity:
            manifest = {
                "slug": slug,
                "packs": CANONICAL_PACK_FILENAMES,
                "kpi": dict(KPI_TARGETS),
            }
            json_write(target / "Agent_Manifest.json", manifest)
            report = integrity_report(profile, packs)
            json_write(target / "INTEGRITY_REPORT.json", report)
            try:
                attach_integrity_to_reporting_pack(report, packs)
                updated_reporting = packs.get("18_Reporting-Pack_v2.json")
                if isinstance(updated_reporting, Mapping):
                    json_write(target / "18_Reporting-Pack_v2.json", updated_reporting)
            except Exception:
                pass

        # Build log
        lines = ["Build OK", f"Slug: {slug}"]
        (target / "build_log.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        if verbose:
            print(f"OK: wrote repo to {target}")
        return 0
    finally:
        lock.release()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build deterministic 20-pack NEO agent repos")
    parser.add_argument("--intake", required=True, type=Path, help="Path to intake profile JSON")
    parser.add_argument("--out", required=True, type=Path, help="Directory to place generated repos")
    parser.add_argument("--extend", action="store_true", help="Extend with defaults for missing reporting templates and connectors")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--strict", action="store_true", help="Fail on non-critical deviations")
    parser.add_argument("--force-utf8", action="store_true", help="Replace invalid UTF-8 bytes when reading intake")
    parser.add_argument("--emit-parity", action="store_true", help="Emit Agent_Manifest.json and INTEGRITY_REPORT.json")

    args = parser.parse_args(argv)
    return build_repo(args.intake, args.out, extend=args.extend, strict=args.strict, verbose=args.verbose, force_utf8=args.force_utf8, emit_parity=args.emit_parity)


if __name__ == "__main__":  # pragma: no cover - exercised via CI wrapper
    raise SystemExit(main())
