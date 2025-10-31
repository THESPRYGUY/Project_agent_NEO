#!/usr/bin/env python
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List


def run(cmd: List[str]) -> tuple[int, str]:
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()
    code = p.returncode
    if code != 0:
        raise SystemExit(f"Command failed ({code}): {' '.join(cmd)}\n{err}")
    return code, out.strip()


def main() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "THESPRYGUY/Project_agent_NEO")
    root = Path(r"C:\\Users\\spryg\\OneDrive\\Documents\\GitHub\\Project_agent_NEO\\generated_repos")
    blanks = root / "reports" / "blanks_audit.json"
    if not blanks.exists():
        print("NO_AUDIT_JSON")
        return 0
    findings = json.loads(blanks.read_text(encoding="utf-8"))
    # Group by project
    by_project: Dict[str, List[dict]] = {}
    for f in findings:
        by_project.setdefault(f.get("project", "unknown"), []).append(f)

    created: List[str] = []
    for project, items in by_project.items():
        p0 = len([x for x in items if (x.get("severity") or "").upper() == "CRITICAL"])  # should be 0
        p1 = len([x for x in items if (x.get("severity") or "").upper() == "HIGH"])  # treat HIGH as P1
        p2 = len([x for x in items if (x.get("key_path") or "").endswith("suggested_traits")])
        if (p1 + p2) == 0:
            continue
        title = f"Generated build blanks (P1/P2) — {project}"
        # Skip if already exists
        try:
            code, out = run(["gh", "issue", "list", "-R", repo, "--state", "open", "--search", f"in:title '{title}'", "--json", "title"])
            if out.strip() and out.strip() != "[]":
                continue
        except SystemExit:
            pass  # Tolerate list failures; continue

        # Top 20 for body
        sev_rank = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1}
        items_sorted = sorted(items, key=lambda x: (-sev_rank.get((x.get("severity") or "").upper(), 0), x.get("file", "")))
        top = items_sorted[:20]
        lines = [f"- [ ] [{f.get('severity')}] {f.get('issue_type')} — `{f.get('key_path')}` in `{Path(f.get('file','')).name}`" for f in top]
        body = (
            f"Audit summary for project: **{project}**\n"
            f"Counts: P0={p0} | HIGH={p1} | P2(persona_traits)={p2}\n"
            "Top 20 findings:\n" + "\n".join(lines) + "\n\n"
            "See BLANKS_AUDIT.md under generated_repos/docs for full details."
        )
        try:
            code, url = run(["gh", "issue", "create", "-R", repo, "-t", title, "-b", body, "-l", "tech-debt,blanks-audit", "-m", "v2.1.2"])
            created.append(url)
        except SystemExit as e:
            print(str(e))
            continue

    if created:
        print("\n".join(created))
    else:
        print("NO_ISSUES_CREATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

