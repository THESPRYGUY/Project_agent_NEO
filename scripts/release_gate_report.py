#!/usr/bin/env python
"""Generate a release gate report from lifecycle artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

DEFAULT_ROOT = Path("generated_repos/agent-build-007-2-1-1")
DEFAULT_OUT = Path("reports")
REPORT_VERSION = "1.0.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarise go-live and rollback readiness from lifecycle pack.",
    )
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Path to build root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Directory for report outputs.")
    return parser.parse_args()


def resolve_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def load_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        raise SystemExit(f"missing required input: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, Mapping):
        raise SystemExit(f"expected object in {path}")
    return data


def as_list(value: Any) -> Sequence[Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def determine_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def iso_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def summarise_checklists(checklists: Sequence[Mapping[str, Any]]) -> Sequence[Dict[str, Any]]:
    summary = []
    for item in checklists:
        if not isinstance(item, Mapping):
            continue
        summary.append(
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or item.get("owner") or ""),
                "owner": str(item.get("owner") or ""),
                "steps": [str(step) for step in as_list(item.get("steps"))],
                "triggers": [str(trigger) for trigger in as_list(item.get("triggers"))],
            }
        )
    return summary


def summarise_phases(phases: Sequence[Mapping[str, Any]]) -> Sequence[Dict[str, Any]]:
    summary = []
    for phase in phases:
        if not isinstance(phase, Mapping):
            continue
        summary.append(
            {
                "id": str(phase.get("id") or ""),
                "name": str(phase.get("name") or ""),
                "owner": str(phase.get("owner") or ""),
                "checks": [str(check) for check in as_list(phase.get("checks"))],
                "evidence": [str(ev) for ev in as_list(phase.get("evidence"))],
            }
        )
    return summary


def approvals_matrix(approvals: Mapping[str, Any]) -> Sequence[Dict[str, Any]]:
    matrix = approvals.get("matrix")
    if not isinstance(matrix, Sequence):
        return []
    items = []
    for entry in matrix:
        if not isinstance(entry, Mapping):
            continue
        items.append(
            {
                "artifact": str(entry.get("artifact") or ""),
                "required": [str(person) for person in as_list(entry.get("required"))],
            }
        )
    return items


def build_report(lifecycle_pack: Mapping[str, Any]) -> Dict[str, Any]:
    go_live = as_mapping(lifecycle_pack.get("go_live"))
    rollback = as_mapping(lifecycle_pack.get("rollback"))
    gates = as_mapping(lifecycle_pack.get("gates"))
    approvals = as_mapping(lifecycle_pack.get("approvals"))

    go_live_checklists = summarise_checklists(as_list(go_live.get("checklists")))
    rollback_checklists = summarise_checklists(as_list(rollback.get("checklists")))

    report = {
        "version": REPORT_VERSION,
        "timestamp": iso_timestamp(),
        "commit": determine_commit(),
        "go_live": {
            "blockers": [str(blocker) for blocker in as_list(go_live.get("blockers"))],
            "phases": summarise_phases(as_list(go_live.get("phases"))),
            "checklists": go_live_checklists,
        },
        "gates": {
            "activation": [str(item) for item in as_list(gates.get("activation"))],
            "kpi_targets": as_mapping(gates.get("kpi_targets")),
            "effective_autonomy": gates.get("effective_autonomy"),
        },
        "approvals": approvals_matrix(approvals),
        "rollback": {
            "on_failure": str(rollback.get("on_failure") or ""),
            "checklists": rollback_checklists,
        },
    }
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Release Gate Report",
        "",
        f"Timestamp: {report.get('timestamp', '')}",
        f"Commit: {report.get('commit', '')}",
        "",
        "## Gate Summary",
    ]
    gates = as_mapping(report.get("gates"))
    activation = gates.get("activation") or []
    if activation:
        lines.append(f"- Activation gates: {', '.join(activation)}")
    kpi_targets = as_mapping(gates.get("kpi_targets"))
    if kpi_targets:
        lines.append(
            "- KPI targets: "
            + ", ".join(f"{key}={value}" for key, value in kpi_targets.items())
        )
    eff = gates.get("effective_autonomy")
    if eff is not None:
        lines.append(f"- Effective autonomy: {eff}")

    lines.append("")
    lines.append("## Go-Live Checklists")
    for checklist in report.get("go_live", {}).get("checklists", []):
        lines.append(f"### {checklist.get('title') or checklist.get('id')}")
        lines.append(f"- Owner: {checklist.get('owner', '')}")
        steps = checklist.get("steps") or []
        if steps:
            lines.append("- Steps:")
            for step in steps:
                lines.append(f"  - {step}")
        triggers = checklist.get("triggers") or []
        if triggers:
            lines.append("- Triggers: " + ", ".join(triggers))
        lines.append("")

    lines.append("## Rollback Checklists")
    for checklist in report.get("rollback", {}).get("checklists", []):
        lines.append(f"### {checklist.get('title') or checklist.get('id')}")
        lines.append(f"- Owner: {checklist.get('owner', '')}")
        triggers = checklist.get("triggers") or []
        if triggers:
            lines.append("- Triggers: " + ", ".join(triggers))
        steps = checklist.get("steps") or []
        if steps:
            lines.append("- Steps:")
            for step in steps:
                lines.append(f"  - {step}")
        lines.append("")

    lines.append("## Approvals Matrix")
    for item in report.get("approvals", []):
        lines.append(f"- {item.get('artifact')}: {', '.join(item.get('required', []))}")

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    args = parse_args()
    root = resolve_path(args.root)
    out_dir = resolve_path(args.out)

    lifecycle_path = root / "17_Lifecycle-Pack_v2.json"
    lifecycle_pack = load_json(lifecycle_path)
    report = build_report(lifecycle_pack)

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "release_gate.json"
    md_path = out_dir / "release_gate.md"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"Wrote {json_path} and {md_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
