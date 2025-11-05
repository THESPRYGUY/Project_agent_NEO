#!/usr/bin/env python
"""Generate KPI report summarizing key metrics and gating context."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from neo_agent import telemetry
from neo_agent.logging import get_logger

LOGGER = get_logger("kpi_report")

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_BUILD_ROOT = REPO_ROOT / "generated_repos" / "agent-build-007-2-1-1"
DEFAULT_OUT_DIR = REPO_ROOT / "reports"
TEMPLATE_PATH = REPO_ROOT / "docs" / "kpi_report.md.tmpl"
REPORT_VERSION = "1.0.0"

DEFAULT_TEMPLATE = """# KPI Report
Timestamp: {timestamp}
Commit: {commit}
Version: {version}

## KPI Snapshot
- PRI: {pri_summary}
- HAL: {hal_summary}
- AUD: {aud_summary}

## Gates Overview
{gates_summary}

## Recent CI Runs ({ci_count})
{ci_summary}
"""


class TemplateValues(dict):
    """Helper allowing safe ``str.format_map`` expansion."""

    def __missing__(self, key: str) -> str:  # noqa: D401
        return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate PRI/HAL/AUD KPI report from build artifacts.",
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_BUILD_ROOT),
        help="Path to build root (expects packs 02, 11, 14, 15).",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT_DIR),
        help="Directory to write report outputs (JSON + Markdown).",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Print concise summary suitable for CI logs.",
    )
    return parser.parse_args()


def resolve_path(value: str, base: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


def load_json_map(path: Path) -> Mapping[str, Any] | None:
    if not path.exists():
        LOGGER.warning("missing input file path=%s", path)
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        LOGGER.error("schema error path=%s detail=%s", path, exc)
        raise SystemExit(2) from exc
    if not isinstance(data, Mapping):
        LOGGER.error("schema error path=%s detail=expected object", path)
        raise SystemExit(2)
    return data


def load_json_any(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        LOGGER.warning("skipping ci artifact path=%s error=%s", path, exc)
        return None


def format_decimal(value: Any) -> str:
    if isinstance(value, (int, float)):
        text = f"{float(value):.6f}".rstrip("0").rstrip(".")
        return text or "0"
    return ""


def locate_kpi_entry(kpis: Sequence[Any], metric_id: str) -> Mapping[str, Any] | None:
    for item in kpis:
        if isinstance(item, Mapping) and item.get("id") == metric_id:
            return item
    return None


def build_metric(metric_id: str, targets: Mapping[str, Any], kpis: Sequence[Any]) -> Dict[str, Any]:
    comparator = ">="
    target_key = f"{metric_id}_min"
    if metric_id.upper() == "HAL":
        comparator = "<="
        target_key = f"{metric_id}_max"

    fallback_value = None
    raw_target = targets.get(target_key) if isinstance(targets, Mapping) else None
    if isinstance(raw_target, (int, float)):
        fallback_value = float(raw_target)

    entry = locate_kpi_entry(kpis, metric_id)
    target_text = ""
    if isinstance(entry, Mapping):
        candidate = entry.get("target")
        if isinstance(candidate, str):
            target_text = candidate.strip()

    if not target_text and fallback_value is not None:
        target_text = f"{comparator}{format_decimal(fallback_value)}"

    value = fallback_value
    status = "target-only" if target_text else "missing-target"
    actual_comparator = comparator

    if target_text:
        stripped = target_text.replace(" ", "")
        for prefix in (">=", "<=", ">", "<", "="):
            if stripped.startswith(prefix):
                actual_comparator = prefix
                numeric_part = stripped[len(prefix) :].strip()
                try:
                    value = float(numeric_part)
                except ValueError:
                    value = fallback_value
                break
        else:
            try:
                value = float(stripped)
            except ValueError:
                value = fallback_value

    if value is None:
        status = "missing-target"

    metric = {
        "metric": metric_id,
        "target": target_text,
        "comparator": actual_comparator,
        "value": value,
        "status": status,
        "source": "targets" if target_text else "unknown",
    }
    return metric


def copy_mapping(mapping: Any) -> Dict[str, Any]:
    if not isinstance(mapping, Mapping):
        return {}
    return {str(key): mapping[key] for key in mapping if isinstance(key, str)}


def build_gates(
    kpi_pack: Mapping[str, Any] | None,
    workflow_pack: Mapping[str, Any] | None,
    global_pack: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    if isinstance(kpi_pack, Mapping):
        gates = kpi_pack.get("gates")
        if isinstance(gates, Mapping):
            summary["activation"] = copy_mapping(gates.get("activation"))
            summary["change"] = copy_mapping(gates.get("change"))
    if isinstance(workflow_pack, Mapping):
        wf_gates = workflow_pack.get("gates")
        if isinstance(wf_gates, Mapping):
            summary["workflow_targets"] = copy_mapping(wf_gates.get("kpi_targets") or {})
    if isinstance(global_pack, Mapping):
        go_live = global_pack.get("go_live")
        if isinstance(go_live, Mapping):
            gates = go_live.get("gates")
            if isinstance(gates, list):
                summary["global_go_live"] = [str(item) for item in gates]
    return summary


def iter_runs(data: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(data, Mapping):
        runs = data.get("runs")
        if isinstance(runs, list):
            for item in runs:
                if isinstance(item, Mapping):
                    yield item
        else:
            yield data
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, Mapping):
                yield item


def normalize_ci_run(raw: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}

    def clean(value: Any) -> str:
        if value in (None, ""):
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return format_decimal(value)
        return str(value)

    run_id = clean(raw.get("id") or raw.get("run_id") or raw.get("runId") or raw.get("number"))
    status = clean(raw.get("status") or raw.get("conclusion") or raw.get("result")) or "unknown"
    url = clean(raw.get("url") or raw.get("html_url"))
    timestamp = clean(
        raw.get("timestamp")
        or raw.get("created_at")
        or raw.get("started_at")
        or raw.get("run_started_at")
    )
    workflow = clean(raw.get("workflow") or raw.get("workflow_name"))
    number = clean(raw.get("number") or raw.get("run_number"))

    if not run_id and number:
        run_id = number
    if not run_id and url:
        run_id = url.rsplit("/", 1)[-1]

    if not (run_id or status or url or timestamp):
        return {}

    entry: Dict[str, Any] = {
        "id": run_id,
        "status": status or "unknown",
        "url": url,
        "timestamp": timestamp,
    }
    if workflow:
        entry["workflow"] = workflow
    if number and number != run_id:
        entry["number"] = number
    source = raw.get("source")
    if isinstance(source, str) and source:
        entry["source"] = source
    return entry


def run_from_env() -> Dict[str, Any] | None:
    run_id = os.environ.get("GITHUB_RUN_ID")
    if not run_id:
        return None

    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    url = ""
    if repository:
        url = f"{server}/{repository}/actions/runs/{run_id}"

    workflow = os.environ.get("GITHUB_WORKFLOW", "")
    number = os.environ.get("GITHUB_RUN_NUMBER", "")
    timestamp = os.environ.get("GITHUB_RUN_STARTED_AT") or os.environ.get("GITHUB_RUN_CREATED_AT") or ""

    entry: Dict[str, Any] = {
        "id": run_id,
        "status": os.environ.get("CI_JOB_STATUS", "unknown") or "unknown",
        "url": url,
        "timestamp": timestamp,
        "source": "env",
    }
    if workflow:
        entry["workflow"] = workflow
    if number:
        entry["number"] = number
    return entry


def collect_ci_runs(root: Path) -> List[Dict[str, Any]]:
    runs: Dict[str, Dict[str, Any]] = {}

    candidates = list(root.glob("ci_runs*.json"))
    reports_dir = root / "reports"
    if reports_dir.exists():
        candidates.extend(reports_dir.glob("ci_runs*.json"))

    for candidate in candidates:
        data = load_json_any(candidate)
        if data is None:
            continue
        for item in iter_runs(data):
            normalised = normalize_ci_run(item)
            if not normalised:
                continue
            run_id = normalised.get("id") or f"run-{len(runs) + 1}"
            normalised["id"] = run_id
            runs[run_id] = normalised

    env_run = run_from_env()
    if env_run:
        runs[env_run["id"]] = env_run

    sorted_runs = sorted(
        runs.values(),
        key=lambda run: run.get("timestamp") or "",
        reverse=True,
    )
    return sorted_runs[:5]


def describe_metric(metric: Mapping[str, Any] | None) -> str:
    if not isinstance(metric, Mapping):
        return "n/a"
    value_text = metric_value_text(metric.get("value"))
    target_text = metric.get("target") or ""
    status = metric.get("status") or ""
    parts: List[str] = []
    if value_text:
        parts.append(f"value {value_text}")
    if target_text:
        parts.append(f"target {target_text}")
    if status:
        parts.append(status)
    if not parts:
        return "n/a"
    return ", ".join(parts)


def metric_value_text(value: Any) -> str:
    if isinstance(value, (int, float)):
        return format_decimal(value)
    return ""


def metric_short(metric: Mapping[str, Any] | None) -> str:
    if not isinstance(metric, Mapping):
        return "n/a"
    value_text = metric_value_text(metric.get("value"))
    target_text = metric.get("target") or ""
    if value_text and target_text:
        return f"{value_text}({target_text})"
    if value_text:
        return value_text
    if target_text:
        return target_text
    return "n/a"


def normalise_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return format_decimal(value)
    if value is None:
        return "n/a"
    return str(value)


def describe_gates(gates: Mapping[str, Any] | None) -> str:
    if not isinstance(gates, Mapping) or not gates:
        return "none"
    lines: List[str] = []
    for name, payload in gates.items():
        if isinstance(payload, Mapping):
            items = ", ".join(f"{key}={normalise_value(payload[key])}" for key in sorted(payload))
            lines.append(f"- {name}: {items or 'n/a'}")
        elif isinstance(payload, list):
            items = ", ".join(str(item) for item in payload) or "n/a"
            lines.append(f"- {name}: {items}")
        else:
            lines.append(f"- {name}: {normalise_value(payload)}")
    return "\n".join(lines) or "none"


def describe_ci_runs(runs: Sequence[Mapping[str, Any]] | None) -> str:
    if not runs:
        return "none"
    lines: List[str] = []
    for run in runs:
        if not isinstance(run, Mapping):
            continue
        run_id = run.get("id") or run.get("number") or "run"
        status = run.get("status") or "unknown"
        workflow = run.get("workflow") or ""
        timestamp = run.get("timestamp") or ""
        url = run.get("url") or ""
        parts = [f"{run_id} ({status})"]
        if workflow:
            parts.append(workflow)
        if timestamp:
            parts.append(timestamp)
        if url:
            parts.append(url)
        lines.append(f"- {' — '.join(parts)}")
    return "\n".join(lines) or "none"


def build_template_context(report: Mapping[str, Any]) -> Dict[str, str]:
    ci_runs = report.get("ci_runs") or []
    if isinstance(ci_runs, list):
        ci_runs_count = len(ci_runs)
    else:  # pragma: no cover - defensive
        ci_runs_count = 0
    context = {
        "timestamp": str(report.get("timestamp", "")),
        "commit": str(report.get("commit", "")),
        "version": str(report.get("version", "")),
        "pri_summary": describe_metric(report.get("pri")),
        "hal_summary": describe_metric(report.get("hal")),
        "aud_summary": describe_metric(report.get("aud")),
        "gates_summary": describe_gates(report.get("gates")),
        "ci_summary": describe_ci_runs(ci_runs if isinstance(ci_runs, list) else []),
        "ci_count": str(ci_runs_count),
    }
    return context


def generate_markdown(report: Mapping[str, Any]) -> str:
    if TEMPLATE_PATH.exists():
        template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    else:
        LOGGER.warning("template missing path=%s (using inline default)", TEMPLATE_PATH)
        template_text = DEFAULT_TEMPLATE
    context = TemplateValues(build_template_context(report))
    try:
        return template_text.format_map(context)
    except KeyError as exc:  # pragma: no cover - defensive
        LOGGER.error("template placeholder missing=%s", exc)
        raise SystemExit(2) from exc


def determine_commit() -> str:
    commit = os.environ.get("GITHUB_SHA")
    if commit:
        return commit
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:  # pragma: no cover - git may be unavailable
        return ""
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def main() -> int:
    args = parse_args()
    cwd = Path.cwd()
    root_path = resolve_path(args.root, cwd)
    out_path = resolve_path(args.out, cwd)

    if not root_path.exists():
        LOGGER.error("build root not found path=%s", root_path)
        return 1

    kpi_pack = load_json_map(root_path / "14_KPI+Evaluation-Framework_v2.json") or {}
    workflow_pack = load_json_map(root_path / "11_Workflow-Pack_v2.json") or {}
    global_pack = load_json_map(root_path / "02_Global-Instructions_v2.json") or {}
    _ = load_json_map(root_path / "15_Observability+Telemetry_Spec_v2.json") or {}

    targets = kpi_pack.get("targets") if isinstance(kpi_pack, Mapping) else {}
    kpis = kpi_pack.get("kpis") if isinstance(kpi_pack, Mapping) else []

    pri_metric = build_metric("PRI", targets, kpis if isinstance(kpis, list) else [])
    hal_metric = build_metric("HAL", targets, kpis if isinstance(kpis, list) else [])
    aud_metric = build_metric("AUD", targets, kpis if isinstance(kpis, list) else [])
    gates = build_gates(kpi_pack, workflow_pack, global_pack)
    ci_runs = collect_ci_runs(root_path)

    report = {
        "version": REPORT_VERSION,
        "timestamp": current_timestamp(),
        "commit": determine_commit(),
        "pri": pri_metric,
        "hal": hal_metric,
        "aud": aud_metric,
        "gates": gates,
        "ci_runs": ci_runs,
    }

    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "kpi_report.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    markdown = generate_markdown(report)
    md_path = out_path / "kpi_report.md"
    md_path.write_text(markdown, encoding="utf-8")

    event_payload = {
        "version": report["version"],
        "timestamp": report["timestamp"],
        "commit": report["commit"],
        "pri_value": pri_metric.get("value"),
        "pri_status": pri_metric.get("status"),
        "hal_value": hal_metric.get("value"),
        "hal_status": hal_metric.get("status"),
        "aud_value": aud_metric.get("value"),
        "aud_status": aud_metric.get("status"),
        "ci_runs": len(ci_runs),
        "out_dir": str(out_path),
    }
    telemetry.emit_event("kpi_report_generated", event_payload)

    if args.ci:
        summary = (
            f"kpi-report commit={report['commit'] or 'unknown'} "
            f"pri={metric_short(pri_metric)} "
            f"hal={metric_short(hal_metric)} "
            f"aud={metric_short(aud_metric)} "
            f"ci_runs={len(ci_runs)}"
        )
        print(summary.strip())

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
