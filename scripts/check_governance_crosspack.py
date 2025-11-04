#!/usr/bin/env python
"""Governance cross-pack consistency checker.

Validates that generated agent repositories keep key governance and safety
contracts aligned across packs 02, 04, and 05.

Checks performed per repository:
  * Cross-file references between 02<->04<->05 point to the expected filenames.
  * Classification defaults agree between 04.policy, 04 root, and 05.
  * No-impersonation guardrail is enabled consistently.
  * PII flag selections match between packs and avoid `none` mixed with others.
  * Safety pack metadata references the same governance pack.

Exit status: 0 when all repositories pass, non-zero otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

PACK_FILENAMES = {
    "02": "02_Global-Instructions_v2.json",
    "04": "04_Governance+Risk-Register_v2.json",
    "05": "05_Safety+Privacy_Guardrails_v2.json",
}


@dataclass(frozen=True)
class CheckIssue:
    repo: str
    code: str
    message: str


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalise_flags(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return sorted({flag for flag in value if isinstance(flag, str)})


def _is_repo_root(path: Path) -> bool:
    return all((path / name).is_file() for name in PACK_FILENAMES.values())


def _collect_repo_paths(root: Path) -> List[Path]:
    if _is_repo_root(root):
        return [root]
    repos: List[Path] = []
    if root.is_dir():
        for child in sorted(root.iterdir()):
            if child.is_dir() and _is_repo_root(child):
                repos.append(child)
    return repos


def check_repo(repo_root: Path) -> List[CheckIssue]:
    """Run consistency checks for a single generated repository."""
    repo_label = repo_root.name or str(repo_root)
    issues: List[CheckIssue] = []

    packs: dict[str, Any] = {}
    for code in ("02", "04", "05"):
        path = repo_root / PACK_FILENAMES[code]
        try:
            packs[code] = _load_json(path)
        except FileNotFoundError as exc:  # pragma: no cover - handled in integration
            issues.append(
                CheckIssue(repo=repo_label, code="missing_pack", message=f"Missing required pack: {exc.filename}")
            )
            return issues
        except json.JSONDecodeError as exc:  # pragma: no cover - guarded by tests elsewhere
            issues.append(
                CheckIssue(
                    repo=repo_label,
                    code="invalid_json",
                    message=f"Invalid JSON in {path}: {exc.msg} (line {exc.lineno}, column {exc.colno}).",
                )
            )
            return issues

    data02 = packs["02"]
    data04 = packs["04"]
    data05 = packs["05"]

    meta04_name = data04.get("meta", {}).get("name") or PACK_FILENAMES["04"]
    meta05_name = data05.get("meta", {}).get("name") or PACK_FILENAMES["05"]

    constraints = data02.get("constraints", {})
    expected_04 = constraints.get("governance_file")
    expected_05 = constraints.get("safety_privacy_file")
    playbook_source = data02.get("refusals", {}).get("playbooks_source")

    if expected_04 != meta04_name:
        issues.append(
            CheckIssue(
                repo=repo_label,
                code="bad_reference_02_to_04",
                message=f"02.constraints.governance_file expected '{meta04_name}' but was '{expected_04}'.",
            )
        )
    if expected_05 != meta05_name:
        issues.append(
            CheckIssue(
                repo=repo_label,
                code="bad_reference_02_to_05",
                message=f"02.constraints.safety_privacy_file expected '{meta05_name}' but was '{expected_05}'.",
            )
        )
    if playbook_source != meta05_name:
        issues.append(
            CheckIssue(
                repo=repo_label,
                code="bad_playbooks_source",
                message=f"02.refusals.playbooks_source expected '{meta05_name}' but was '{playbook_source}'.",
            )
        )

    privacy_alignment = data04.get("privacy_alignment", {})
    guardrails_ref = privacy_alignment.get("guardrails_file")
    if guardrails_ref != meta05_name:
        issues.append(
            CheckIssue(
                repo=repo_label,
                code="bad_reference_04_to_05",
                message=f"04.privacy_alignment.guardrails_file expected '{meta05_name}' but was '{guardrails_ref}'.",
            )
        )

    operational_hooks = data05.get("operational_hooks", {})
    governance_ref = operational_hooks.get("governance_file")
    if governance_ref and governance_ref != meta04_name:
        issues.append(
            CheckIssue(
                repo=repo_label,
                code="bad_reference_05_to_04",
                message=f"05.operational_hooks.governance_file expected '{meta04_name}' but was '{governance_ref}'.",
            )
        )

    cls_root = data04.get("classification_default")
    cls_policy = data04.get("policy", {}).get("classification_default")
    cls_05 = data05.get("data_classification", {}).get("default")
    cls_labels = data05.get("data_classification", {}).get("labels") or []

    if not cls_root:
        issues.append(
            CheckIssue(repo=repo_label, code="missing_classification_04", message="04.classification_default missing.")
        )
    if not cls_policy:
        issues.append(
            CheckIssue(
                repo=repo_label, code="missing_classification_policy", message="04.policy.classification_default missing."
            )
        )
    if not cls_05:
        issues.append(
            CheckIssue(
                repo=repo_label, code="missing_classification_05", message="05.data_classification.default missing."
            )
        )
    if cls_root and cls_policy and cls_root != cls_policy:
        issues.append(
            CheckIssue(
                repo=repo_label,
                code="classification_mismatch_04",
                message=f"04 classification_default '{cls_root}' != policy value '{cls_policy}'.",
            )
        )
    if cls_root and cls_05 and cls_root != cls_05:
        issues.append(
            CheckIssue(
                repo=repo_label,
                code="classification_mismatch_05",
                message=f"04 classification_default '{cls_root}' != 05 default '{cls_05}'.",
            )
        )
    if cls_root and cls_labels and cls_root not in cls_labels:
        issues.append(
            CheckIssue(
                repo=repo_label,
                code="classification_not_labelled",
                message=f"05.data_classification.labels missing '{cls_root}'.",
            )
        )

    no_imp_04 = data04.get("policy", {}).get("no_impersonation")
    no_imp_05 = data05.get("no_impersonation")
    if no_imp_04 is not True or no_imp_05 is not True:
        issues.append(
            CheckIssue(
                repo=repo_label,
                code="no_impersonation_disabled",
                message=f"No-impersonation guardrail mismatch (04={no_imp_04}, 05={no_imp_05}).",
            )
        )

    flags_04 = _normalise_flags(data04.get("pii_flags"))
    flags_04_priv = _normalise_flags(privacy_alignment.get("pii_flags"))
    flags_05 = _normalise_flags(data05.get("pii_flags"))
    if not flags_05:
        flags_05 = _normalise_flags(data05.get("privacy_policies", {}).get("pii_flags"))

    if not flags_04:
        issues.append(
            CheckIssue(repo=repo_label, code="missing_pii_flags_04", message="04.pii_flags is empty.")
        )
    if not flags_05:
        issues.append(
            CheckIssue(repo=repo_label, code="missing_pii_flags_05", message="05.pii_flags is empty.")
        )

    if flags_04 and flags_05 and flags_04 != flags_05:
        issues.append(
            CheckIssue(
                repo=repo_label,
                code="pii_flags_mismatch",
                message=f"04.pii_flags {flags_04} != 05.pii_flags {flags_05}.",
            )
        )
    if flags_04_priv:
        expected_flags = set(flags_04) | set(flags_05)
        if expected_flags and not expected_flags.issubset(set(flags_04_priv)):
            issues.append(
                CheckIssue(
                    repo=repo_label,
                    code="pii_flags_privacy_alignment_mismatch",
                    message=f"04.privacy_alignment.pii_flags {flags_04_priv} missing selections from packs (expected subset of {sorted(expected_flags)}).",
                )
            )

    for label, flags in (("04.pii_flags", flags_04), ("05.pii_flags", flags_05)):
        if "none" in flags and len(flags) > 1:
            issues.append(
                CheckIssue(
                    repo=repo_label,
                    code="pii_flags_none_combo",
                    message=f"{label} mixes 'none' with other flags: {flags}.",
                )
            )

    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-check governance packs 02<->04<->05 for consistency.")
    default_root = Path(os.environ.get("BUILD_ROOT", "generated_repos/agent-build-007-2-1-1"))
    parser.add_argument(
        "--root",
        type=Path,
        default=default_root,
        help="Path to the generated repo to check (default: %(default)s).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code when findings are detected.",
    )
    args = parser.parse_args(argv)

    repo_root = args.root.expanduser().resolve()
    if not _is_repo_root(repo_root):
        parser.error(
            f"{repo_root} does not contain required packs {tuple(PACK_FILENAMES.values())}. "
            "Set BUILD_ROOT or pass --root to a generated repo root."
        )

    repo_issues = check_repo(repo_root)
    if repo_issues:
        print(f"[FAIL] {repo_root.name} ({len(repo_issues)} issue(s)).")
        for issue in repo_issues:
            print(f"  - [{issue.code}] {issue.message}")
        if args.strict:
            return 1
        print("\nGovernance cross-check completed with findings (non-strict mode).")
        return 0

    print(f"[OK] {repo_root.name} governance cross-check passed.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
