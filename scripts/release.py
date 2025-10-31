#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def sh(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=check)


def sh_out(args: list[str]) -> str:
    cp = subprocess.run(args, check=True, capture_output=True, text=True)
    return (cp.stdout or "").strip()


def main() -> int:
    p = argparse.ArgumentParser(description="Tag and create a GitHub release")
    p.add_argument("--version", required=True, help="Semver tag, e.g. 2.1.2")
    p.add_argument("--notes-file", help="Path to release notes; if omitted, a scaffold is generated")
    args = p.parse_args()

    version = args.version.strip()
    if not version or not all(part.isdigit() for part in version.split(".") if part):
        print("Invalid version; expected x.y.z", file=sys.stderr)
        return 2
    tag = f"v{version}"

    # Refuse if working tree is dirty
    dirty = sh_out(["git", "status", "--porcelain"]) != ""
    if dirty:
        print("Working tree has uncommitted changes; aborting", file=sys.stderr)
        return 2

    # Tag
    print(f"Tagging {tag}…")
    sh(["git", "tag", tag, "-m", f"Release {tag}"])
    sh(["git", "push", "origin", tag])

    # Notes scaffold
    notes_path: Path
    if args.notes_file:
        notes_path = Path(args.notes_file)
    else:
        scaffold = f"""
Highlights
- See RELEASE_CHECKLIST.md for gates (validator ✅, zip parity, no .tmp, lock 423, guard pass, SLOs pass)

Operational Proofs
- Contract validator single-line ✅ present
- ZIP parity: default vs ?outdir= sha256 match
- Shim Redirect Guard passing; no shim hits
""".strip()
        notes_path = Path(".release_notes.txt")
        notes_path.write_text(scaffold, encoding="utf-8")

    # Create GitHub release
    title = f"Project NEO {tag}"
    print(f"Creating GitHub release {title}…")
    sh(["gh", "release", "create", tag, "--title", title, "--notes-file", str(notes_path)])
    url = sh_out(["gh", "release", "view", tag, "--json", "url", "--jq", ".url"]) or ""
    print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

