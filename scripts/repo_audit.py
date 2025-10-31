#!/usr/bin/env python
"""Generated Repos Auditor

Scans generated agent repos for blank/omitted/placeholder fields and emits
machine-readable findings plus a human summary.

Outputs (under --root):
  - reports/blanks_audit.json
  - reports/blanks_audit.csv
  - docs/BLANKS_AUDIT.md
  - docs/BLANKS_REMEDIATION_PLAN.md (remediation suggestions)

CLI:
  python scripts/repo_audit.py \
    --root "C:\\Users\\spryg\\OneDrive\\Documents\\GitHub\\Project_agent_NEO\\generated_repos" \
    --format md,json,csv --fail-on critical
"""

from __future__ import annotations

import argparse
import ast
import csv as _csv
import io
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple, Union


# Optional deps available in this repo
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

try:  # Python 3.11+
    import tomllib  # type: ignore
except Exception:  # pragma: no cover
    tomllib = None

try:
    from neo_build.schemas import required_keys_map
    from neo_build.contracts import CANONICAL_PACK_FILENAMES
except Exception:  # pragma: no cover
    # Fall back to safe defaults when imports fail
    CANONICAL_PACK_FILENAMES = []  # type: ignore

    def required_keys_map():  # type: ignore
        return {}


WINDOWS_TARGET_ROOT = r"C:\\Users\\spryg\\OneDrive\\Documents\\GitHub\\Project_agent_NEO\\generated_repos"

SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


PLACEHOLDER_PATTERNS = [
    r"\bTBD\b",
    r"\bTODO\b",
    r"\bFIXME\b",
    r"\?\?\?",
    r"placeholder",
    r"\bunset\b",
    r"\bn/?a\b",
    r"\bchange\s*me\b",
    r"your-[^\s\"]*-here",
    r"example\.com",
    r"dummy",
]
PLACEHOLDER_RE = re.compile("|".join(PLACEHOLDER_PATTERNS), re.IGNORECASE)


SKIP_DIR_NAMES = {
    "spec_preview",  # transient previews
    ".git",
    "__pycache__",
    "node_modules",
    "_artifacts",
}

TEXT_EXTS = {".json", ".yaml", ".yml", ".toml", ".py", ".js", ".ts", ".md"}
BINARY_EXTS = {
    ".zip",
    ".gz",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
}


@dataclass
class Finding:
    project: str
    file: str
    line: Optional[int]
    key_path: str
    value_snippet: str
    issue_type: str  # one of {missing_required, empty_value, placeholder, deprecated_key, unknown_key}
    severity: str    # CRITICAL, HIGH, MEDIUM, LOW
    suggested_fix_hint: str


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (str, bytes)):
        return len(value) == 0
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def _looks_like_placeholder(text: str) -> bool:
    return bool(PLACEHOLDER_RE.search(text or ""))


def _text_snippet(value: Any, max_len: int = 140) -> str:
    try:
        if isinstance(value, (dict, list)):
            txt = json.dumps(value, ensure_ascii=False)
        else:
            txt = str(value)
    except Exception:
        txt = str(value)
    if len(txt) > max_len:
        return txt[: max_len - 1] + "…"
    return txt


def _project_name(root: Path, file_path: Path) -> str:
    # Project is the top-level folder name directly under root
    try:
        rel = file_path.relative_to(root)
        return rel.parts[0] if len(rel.parts) > 0 else root.name
    except Exception:
        return root.name


def _iter_files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skipped directories in-place
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() in TEXT_EXTS and p.suffix.lower() not in BINARY_EXTS:
                yield p


def _find_line_of_key(lines: List[str], key: str) -> Optional[int]:
    pat = re.compile(rf"\b\"?{re.escape(key)}\"?\b")
    for i, line in enumerate(lines, start=1):
        if pat.search(line):
            return i
    return None


def _flatten(obj: Any, base: str = "") -> Iterator[Tuple[str, Any]]:
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            kp = f"{base}.{k}" if base else str(k)
            yield from _flatten(v, kp)
    elif isinstance(obj, list):
        for idx, v in enumerate(obj):
            kp = f"{base}[{idx}]" if base else f"[{idx}]"
            yield from _flatten(v, kp)
    else:
        yield base, obj


def _analyze_mapping(project: str, file_path: Path, payload: Mapping[str, Any], lines: Optional[List[str]]) -> List[Finding]:
    findings: List[Finding] = []
    name = file_path.name
    for key_path, value in _flatten(payload):
        # P0 classification rules (CRITICAL)
        issue = None
        severity = "HIGH"
        if name == "11_Workflow-Pack_v2.json" and key_path.endswith("defaults.tone") and _is_empty(value):
            issue, severity = "empty_value", "CRITICAL"
        elif name == "06_Role-Recipes_Index_v2.json" and key_path == "role_recipe_ref" and _is_empty(value):
            issue, severity = "empty_value", "CRITICAL"
        elif name == "09_Agent-Manifests_Catalog_v2.json" and key_path.startswith("agents[0].agent_id") and _is_empty(value):
            issue, severity = "empty_value", "CRITICAL"
        # P1 classification rules
        elif name == "19_Overlay-Pack_SME-Domain_v1.json" and key_path in ("industry", "region") and _is_empty(value):
            issue, severity = "empty_value", "HIGH"
        elif name == "04_Governance+Risk-Register_v2.json" and isinstance(value, str) and _looks_like_placeholder(value):
            issue, severity = "placeholder", "MEDIUM"
        # P2 classification (persona traits length < 3)
        elif key_path.endswith("suggested_traits") and isinstance(value, list) and len(value) < 3:
            issue, severity = "empty_value", "MEDIUM"

        if issue is None and _is_empty(value):
            issue, severity = "empty_value", "HIGH"

        if issue is not None:
            line = _find_line_of_key(lines or [], key_path.split(".")[-1]) if lines else None
            findings.append(Finding(
                project=project,
                file=str(file_path),
                line=line,
                key_path=key_path,
                value_snippet=_text_snippet(value),
                issue_type=issue,
                severity=severity,
                suggested_fix_hint="Provide a non-empty value; remove if optional.",
            ))
        elif isinstance(value, str) and _looks_like_placeholder(value):
            line = _find_line_of_key(lines or [], key_path.split(".")[-1]) if lines else None
            findings.append(Finding(
                project=project,
                file=str(file_path),
                line=line,
                key_path=key_path,
                value_snippet=_text_snippet(value),
                issue_type="placeholder",
                severity="MEDIUM",
                suggested_fix_hint="Replace placeholder text with finalized content.",
            ))
    return findings


def _check_pack_required_keys(project: str, file_path: Path, payload: Mapping[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    req_map = required_keys_map() or {}
    name = file_path.name
    required = req_map.get(name)
    if not required:
        return findings
    present = set(payload.keys())
    for key in required:
        if key not in present:
            findings.append(Finding(
                project=project,
                file=str(file_path),
                line=None,
                key_path=key,
                value_snippet="(missing)",
                issue_type="missing_required",
                severity="CRITICAL",
                suggested_fix_hint=f"Add required top-level key '{key}' per contract.",
            ))
    return findings


def _scan_text_placeholders(project: str, file_path: Path, content: str) -> List[Finding]:
    findings: List[Finding] = []
    for i, line in enumerate(content.splitlines(), start=1):
        if _looks_like_placeholder(line):
            findings.append(Finding(
                project=project,
                file=str(file_path),
                line=i,
                key_path="(line)",
                value_snippet=line.strip()[:140],
                issue_type="placeholder",
                severity="MEDIUM",
                suggested_fix_hint="Replace placeholder token in documentation/source.",
            ))
    return findings


def _analyze_json_yaml_toml(project: str, file_path: Path, text: str) -> List[Finding]:
    findings: List[Finding] = []
    payload: Optional[Mapping[str, Any]] = None
    try:
        if file_path.suffix.lower() == ".json":
            payload = json.loads(text)
        elif file_path.suffix.lower() in {".yaml", ".yml"} and yaml is not None:
            payload = yaml.safe_load(text)
        elif file_path.suffix.lower() == ".toml" and tomllib is not None:
            payload = tomllib.loads(text)
    except Exception:
        payload = None

    findings.extend(_scan_text_placeholders(project, file_path, text))

    if isinstance(payload, Mapping):
        lines = text.splitlines()
        findings.extend(_analyze_mapping(project, file_path, payload, lines))
        findings.extend(_check_pack_required_keys(project, file_path, payload))
    return findings


def _constant_value(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_constant_value(e) for e in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_constant_value(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        out = {}
        for k, v in zip(node.keys, node.values):
            key = _constant_value(k)
            out[key] = _constant_value(v)
        return out
    return None


def _analyze_python(project: str, file_path: Path, text: str) -> List[Finding]:
    findings: List[Finding] = []
    try:
        tree = ast.parse(text)
    except Exception:
        return _scan_text_placeholders(project, file_path, text)

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self._findings: List[Finding] = []

        def visit_Dict(self, node: ast.Dict) -> Any:  # noqa: N802
            kv: Dict[str, Any] = {}
            try:
                for k, v in zip(node.keys, node.values):
                    key = _constant_value(k)
                    if isinstance(key, str):
                        kv[key] = _constant_value(v)
            except Exception:
                kv = {}
            for k, v in kv.items():
                key_path = k
                if _is_empty(v):
                    self._findings.append(Finding(
                        project=project,
                        file=str(file_path),
                        line=getattr(node, "lineno", None),
                        key_path=key_path,
                        value_snippet=_text_snippet(v),
                        issue_type="empty_value",
                        severity="HIGH",
                        suggested_fix_hint="Provide a non-empty value; remove if optional.",
                    ))
                elif isinstance(v, str) and _looks_like_placeholder(v):
                    self._findings.append(Finding(
                        project=project,
                        file=str(file_path),
                        line=getattr(node, "lineno", None),
                        key_path=key_path,
                        value_snippet=_text_snippet(v),
                        issue_type="placeholder",
                        severity="MEDIUM",
                        suggested_fix_hint="Replace placeholder text with finalized content.",
                    ))
            self.generic_visit(node)

    v = Visitor()
    v.visit(tree)
    findings.extend(_scan_text_placeholders(project, file_path, text))
    return findings + v._findings


def _analyze_js_ts(project: str, file_path: Path, text: str) -> List[Finding]:
    # Best-effort: detect placeholders and obviously empty literals
    findings: List[Finding] = []
    findings.extend(_scan_text_placeholders(project, file_path, text))
    obj_pat = re.compile(r"(\"[\w.-]+\"|[\w.-]+)\s*:\s*(\{\s*\}|\[\s*\]|\"\")")
    for i, line in enumerate(text.splitlines(), start=1):
        for m in obj_pat.finditer(line):
            key = m.group(1).strip('"')
            findings.append(Finding(
                project=project,
                file=str(file_path),
                line=i,
                key_path=key,
                value_snippet=m.group(2),
                issue_type="empty_value",
                severity="HIGH",
                suggested_fix_hint="Populate object/array/string with real values.",
            ))
    return findings


def analyze_file(root: Path, file_path: Path) -> List[Finding]:
    project = _project_name(root, file_path)
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    suffix = file_path.suffix.lower()
    if suffix in {".json", ".yaml", ".yml", ".toml"}:
        return _analyze_json_yaml_toml(project, file_path, text)
    if suffix == ".py":
        return _analyze_python(project, file_path, text)
    if suffix in {".js", ".ts"}:
        return _analyze_js_ts(project, file_path, text)
    if suffix == ".md":
        return _scan_text_placeholders(project, file_path, text)
    return []


def severity_rank(level: str) -> int:
    try:
        return SEVERITY_ORDER.index(level.upper())
    except Exception:
        return 0


def _ensure_dirs(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_reports(root: Path, findings: Sequence[Finding], formats: Sequence[str]) -> None:
    reports_dir = root / "reports"
    docs_dir = root / "docs"
    _ensure_dirs(reports_dir)
    _ensure_dirs(docs_dir)

    # JSON
    if any(f for f in formats if f.lower() == "json"):
        payload = [asdict(f) for f in findings]
        (reports_dir / "blanks_audit.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # CSV
    if any(f for f in formats if f.lower() == "csv"):
        csv_path = reports_dir / "blanks_audit.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = _csv.writer(handle)
            writer.writerow(["project", "file", "line", "key_path", "value_snippet", "issue_type", "severity", "suggested_fix_hint"])
            for f in findings:
                writer.writerow([f.project, f.file, f.line or "", f.key_path, f.value_snippet, f.issue_type, f.severity, f.suggested_fix_hint])

    # Markdown summary + Top-20 list
    if any(f for f in formats if f.lower() == "md"):
        md_path = docs_dir / "BLANKS_AUDIT.md"
        md = _render_md_summary(root, findings)
        md_path.write_text(md, encoding="utf-8")

    # Remediation plan (always produced for convenience)
    plan_path = docs_dir / "BLANKS_REMEDIATION_PLAN.md"
    plan_md = _render_remediation_plan(findings)
    plan_path.write_text(plan_md, encoding="utf-8")


def _group_by_project(findings: Sequence[Finding]) -> Dict[str, List[Finding]]:
    out: Dict[str, List[Finding]] = {}
    for f in findings:
        out.setdefault(f.project, []).append(f)
    return out


def _render_md_summary(root: Path, findings: Sequence[Finding]) -> str:
    projects = _group_by_project(findings)
    lines: List[str] = []
    lines.append(f"# Generated Repos Blanks Audit\n")
    lines.append(f"Root: `{root}`\n")
    lines.append("\n## Per-Project Severity Summary\n")
    lines.append("| Project | CRITICAL | HIGH | MED | LOW | Top Offenders (key_path -> file) |")
    lines.append("| - | -: | -: | -: | -: | - |")

    for project, items in sorted(projects.items()):
        c = sum(1 for f in items if f.severity == "CRITICAL")
        h = sum(1 for f in items if f.severity == "HIGH")
        m = sum(1 for f in items if f.severity == "MEDIUM")
        l = sum(1 for f in items if f.severity == "LOW")
        # Top offenders: pick top 3 by severity then frequency
        offenders = sorted(items, key=lambda f: (-severity_rank(f.severity), f.key_path))[:3]
        offenders_txt = ", ".join(f"{o.key_path} -> {Path(o.file).name}" for o in offenders)
        lines.append(f"| {project} | {c} | {h} | {m} | {l} | {offenders_txt} |")

    # Top-20
    lines.append("\n## Top 20 Findings\n")
    top = sorted(findings, key=lambda f: (-severity_rank(f.severity), f.project, f.file))[:20]
    for idx, f in enumerate(top, start=1):
        lines.append(f"{idx}. [{f.severity}] {f.issue_type} — `{f.key_path}` in `{Path(f.file).name}` ({f.project})")
    lines.append("")
    return "\n".join(lines)


def _render_remediation_plan(findings: Sequence[Finding]) -> str:
    lines: List[str] = []
    lines.append("# BLANKS Remediation Plan\n")
    lines.append("Owner default: @THESPRYGUY | Milestone: v2.1.2\n")
    lines.append("| project | file | key_path | issue_type | severity | fix_strategy | owner | ETA |")
    lines.append("| - | - | - | - | - | - | - | - |")
    for f in sorted(findings, key=lambda x: (-severity_rank(x.severity), x.project, x.file, x.key_path)):
        strategy = _suggest_fix_strategy(f)
        lines.append(f"| {f.project} | {Path(f.file).name} | {f.key_path} | {f.issue_type} | {f.severity} | {strategy} | @THESPRYGUY | T+3d |")
    lines.append("")
    return "\n".join(lines)


def _suggest_fix_strategy(f: Finding) -> str:
    kp = f.key_path.lower()
    fname = Path(f.file).name
    if f.issue_type == "missing_required":
        return f"Add required key '{f.key_path}' per contract for {fname}."
    if "suggested_traits" in kp:
        return "Seed 3–5 traits aligned to the selected MBTI (e.g., decisiveness, structure, collaboration)."
    if "kpi" in kp or fname.startswith("14_KPI"):
        return "Populate KPI targets; align 02/11/17 with 14 (use validators.kpi_targets_sync)."
    if "connectors" in kp or "secrets" in kp:
        return "Replace dummy values; scope connectors and provide non-production keys in CI secrets."
    if f.issue_type == "placeholder":
        return "Replace placeholder tokens (TBD/TODO/etc.) with finalized content."
    return f.suggested_fix_hint or "Fill with correct, non-empty value."


def run_audit(root: Union[str, Path], formats: Sequence[str] = ("json", "csv", "md")) -> List[Finding]:
    root = Path(root)
    findings: List[Finding] = []
    if not root.exists():
        return findings
    for fp in _iter_files(root):
        # Skip binary by extension explicitly
        if fp.suffix.lower() in BINARY_EXTS:
            continue
        try:
            file_findings = analyze_file(root, fp)
            findings.extend(file_findings)
        except Exception:
            # Never break the audit; continue
            continue
    # Write reports
    write_reports(root, findings, formats)
    return findings


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Audit generated repos for blank/placeholder/omitted fields")
    p.add_argument("--root", default=WINDOWS_TARGET_ROOT, help="Root folder containing generated repos")
    p.add_argument("--format", default="md,json,csv", help="Comma-separated output formats: md,json,csv")
    p.add_argument("--fail-on", default="", help="Severity threshold to fail the process (e.g., 'critical', 'high')")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    ns = _parse_args(argv or sys.argv[1:])
    formats = [f.strip() for f in (ns.format or "md,json,csv").split(",") if f.strip()]
    findings = run_audit(ns.root, formats)
    threshold = (ns.fail_on or "").strip().upper()
    if threshold:
        worst = max([severity_rank(f.severity) for f in findings], default=0)
        if worst >= severity_rank(threshold):
            return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
