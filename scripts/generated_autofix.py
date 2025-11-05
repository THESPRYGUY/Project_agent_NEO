#!/usr/bin/env python
"""Autofix for generated repos (P0/P1/P2).

Usage:
  python scripts/generated_autofix.py --root "C:\\...\\generated_repos" --dry-run
  python scripts/generated_autofix.py --root "C:\\...\\generated_repos" --write

Behavior:
  - Iterates each project folder under --root
  - Applies P0 fixes (must resolve) and P1/P2 (best effort)
  - Writes changes when --write; otherwise prints a dry-run summary
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from persona.traits_utils import compose_traits  # type: ignore


WINDOWS_TARGET_ROOT = r"C:\\Users\\spryg\\OneDrive\\Documents\\GitHub\\Project_agent_NEO\\generated_repos"


# Utilities

def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _safe_str(v: Any) -> str:
    return str(v) if v is not None else ""


def _has_placeholders(text: str) -> bool:
    patterns = [
        r"\bTBD\b",
        r"\bTODO\b",
        r"\bFIXME\b",
        r"\?\?\?",
        r"placeholder",
        r"\bunset\b",
        r"\bn/?a\b",
        r"\bchange\s*me\b",
    ]
    return bool(re.search("|".join(patterns), text or "", flags=re.IGNORECASE))


def _replace_placeholders(obj: Any, replacements: Mapping[str, str]) -> Any:
    if isinstance(obj, dict):
        return {k: _replace_placeholders(v, replacements) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_placeholders(v, replacements) for v in obj]
    if isinstance(obj, str) and _has_placeholders(obj):
        for pat, subst in replacements.items():
            if re.search(pat, obj, flags=re.IGNORECASE):
                obj = re.sub(pat, subst, obj, flags=re.IGNORECASE)
        return obj
    return obj


def _generate_agent_id(naics_code: str | None, function_code: str | None, role_code: str | None, name: str | None) -> str:
    # Deterministic, readable ID when SoT not available
    n = (naics_code or "000000").strip().replace(":", "-")
    func = (function_code or "UNK").strip().upper().replace(":", "-")
    role = (role_code or "UNK").strip().upper().replace(":", "-")
    suffix = (name or "agent").strip().lower().replace(" ", "-")[:8]
    return f"AGT-{n}-{func}:{role}-{suffix}"[:64]


def _mbti_axes(code: str | None) -> Dict[str, str]:
    code = (code or "").upper()
    labels = ("EI", "SN", "TF", "JP")
    axes: Dict[str, str] = {}
    for idx, label in enumerate(labels):
        axes[label] = code[idx] if len(code) > idx else ""
    return axes


@dataclass
class ProjectResult:
    project: str
    p0_fixed: int = 0
    p0_remaining: int = 0
    p1_fixed: int = 0
    p2_fixed: int = 0
    changes: List[Tuple[str, str]] = None  # (file, description)

    def __post_init__(self) -> None:
        if self.changes is None:
            self.changes = []


def _autofix_project(
    root: Path,
    project_dir: Path,
    *,
    write: bool,
    catalog_mbti: Optional[List[Mapping[str, Any]]],
    traits_lexicon: Mapping[str, Any],
    traits_overlays: Mapping[str, Iterable[str]],
) -> ProjectResult:
    pr = ProjectResult(project=project_dir.name)
    ts = _utc_ts()
    last_build = _read_json(Path.cwd() / "_generated" / "_last_build.json")
    last_agent_id = (last_build or {}).get("agent_id") if isinstance(last_build, dict) else None

    # Load commonly used files (if present)
    paths = {
        "06": project_dir / "06_Role-Recipes_Index_v2.json",
        "07": project_dir / "07_Subagent_Role-Recipes_v2.json",
        "09": project_dir / "09_Agent-Manifests_Catalog_v2.json",
        "11": project_dir / "11_Workflow-Pack_v2.json",
        "19": project_dir / "19_Overlay-Pack_SME-Domain_v1.json",
        "04": project_dir / "04_Governance+Risk-Register_v2.json",
        "02": project_dir / "02_Global-Instructions_v2.json",
        "agent_profile": project_dir / "agent_profile.json",
    }
    data: Dict[str, Any] = {k: (_read_json(p) if p.exists() else None) for k, p in paths.items()}

    # P0.1: role_recipe_ref
    try:
        d06 = data.get("06") or {}
        if isinstance(d06, dict):
            if not _safe_str(d06.get("role_recipe_ref")):
                # Lookup in 07 by role code, else fallback
                role_code = ((d06.get("mapping") or {}).get("primary_role_code") or d06.get("archetype") or "").strip()
                d07 = data.get("07") or {}
                ref: Optional[str] = None
                recipes = d07.get("recipes") if isinstance(d07, dict) else None
                if isinstance(recipes, list):
                    for r in recipes:
                        if not isinstance(r, dict):
                            continue
                        code = _safe_str(r.get("code"))
                        if code and role_code and role_code in _safe_str(r.get("roles") or _safe_str(r.get("role") or "")):
                            ref = code
                            break
                        if not ref and code:
                            ref = code
                if not ref:
                    ref = "AIA-P:Planner-Builder-Evaluator"
                d06["role_recipe_ref"] = ref
                if "notes" in d06:
                    d06["notes"] = f"AUTOFIX {ts}: source={'07' if recipes else 'fallback'}"
                pr.p0_fixed += 1
                pr.changes.append((paths["06"].name, f"role_recipe_ref -> {ref}"))
                if write:
                    _write_json(paths["06"], d06)
    except Exception:
        pr.p0_remaining += 1

    # P0.2: agents[0].agent_id
    try:
        d09 = data.get("09") or {}
        if isinstance(d09, dict):
            agents = d09.get("agents") if isinstance(d09.get("agents"), list) else []
            if agents:
                agent0 = agents[0]
                if not _safe_str(agent0.get("agent_id")):
                    agent_id = None
                    if last_agent_id:
                        agent_id = last_agent_id
                        source = "sot"
                    else:
                        # Fallback: derive from 02 + 06 + name
                        d02 = data.get("02") or {}
                        naics_code = (((d02.get("summary") or {}).get("naics") or {}).get("code") if isinstance(d02, dict) else None)
                        function_code = ((d06.get("mapping") or {}).get("primary_role_code") if isinstance(d06, dict) else None)
                        role_code = function_code
                        name = (agents[0] or {}).get("display_name")
                        agent_id = _generate_agent_id(naics_code, function_code, role_code, name)
                        source = "derived"
                    agent0["agent_id"] = agent_id
                    if "notes" in d09:
                        d09["notes"] = f"AUTOFIX {ts}: source={source}"
                    pr.p0_fixed += 1
                    pr.changes.append((paths["09"].name, f"agents[0].agent_id -> {agent_id}"))
                    if write:
                        _write_json(paths["09"], d09)
    except Exception:
        pr.p0_remaining += 1

    # P0.3: 11 defaults.tone
    try:
        d11 = data.get("11") or {}
        if isinstance(d11, dict):
            defaults = d11.get("defaults") if isinstance(d11.get("defaults"), dict) else {}
            tone = _safe_str(defaults.get("tone"))
            if not tone:
                defaults["tone"] = "crisp, analytical, executive"
                d11["defaults"] = defaults
                if "notes" in d11:
                    d11["notes"] = f"AUTOFIX {ts}: source=fixed"
                pr.p0_fixed += 1
                pr.changes.append((paths["11"].name, "defaults.tone -> 'crisp, analytical, executive'"))
                if write:
                    _write_json(paths["11"], d11)
    except Exception:
        pr.p0_remaining += 1

    # P1.4: 19 overlay industry/region or delete when both absent
    try:
        p19 = paths.get("19")
        d19 = data.get("19")
        if p19 and d19 and isinstance(d19, dict):
            industry = _safe_str(d19.get("industry"))
            region = d19.get("region") if isinstance(d19.get("region"), list) else []
            changed = False
            if not industry:
                # Prefer NAICS title
                title = _safe_str(((d19.get("naics") or {}).get("title")))
                if not title:
                    # Try 02 summary
                    d02 = data.get("02") or {}
                    title = _safe_str((((d02.get("summary") or {}).get("naics") or {}).get("title")))
                if title:
                    d19["industry"] = title
                    changed = True
            if not region:
                d02 = data.get("02") or {}
                region2 = (d02.get("summary") or {}).get("region")
                if isinstance(region2, list) and region2:
                    d19["region"] = region2
                    changed = True
            if changed:
                if "notes" in d19:
                    d19["notes"] = f"AUTOFIX {ts}: source=sot"
                pr.p1_fixed += 1
                pr.changes.append((p19.name, "industry/region populated"))
                if write:
                    _write_json(p19, d19)
            else:
                # If both still empty, delete overlay file
                if (not _safe_str(d19.get("industry"))) and (not (isinstance(d19.get("region"), list) and d19.get("region"))):
                    if write:
                        try:
                            p19.unlink(missing_ok=True)
                        except TypeError:
                            # Python <3.8 compatibility
                            if p19.exists():
                                p19.unlink()
                    pr.p1_fixed += 1
                    pr.changes.append((p19.name, "deleted overlay (insufficient context)"))
    except Exception:
        pass

    # P1.5: Governance placeholders replacement
    try:
        d04 = data.get("04") or {}
        if isinstance(d04, dict):
            raw = json.dumps(d04)
            if _has_placeholders(raw):
                replacements = {
                    r"\bTBD\b": "Defined",
                    r"\bTODO\b": "Defined",
                    r"\bFIXME\b": "Defined",
                    r"placeholder": "Defined",
                }
                d04 = _replace_placeholders(d04, replacements)
                # Ensure minimum anchors
                frameworks = d04.setdefault("frameworks", {})
                regs = frameworks.setdefault("regulators", [])
                for req in ["NIST_AI_RMF", "EU_AI_ACT", "ISO_IEC_42001"]:
                    if req not in regs:
                        regs.append(req)
                # Add owner hints
                owners = d04.setdefault("owners", [])
                if "CAIO" not in owners:
                    owners.append("CAIO")
                if "notes" in d04:
                    d04["notes"] = f"AUTOFIX {ts}: source=baseline"
                pr.p1_fixed += 1
                pr.changes.append((paths["04"].name, "placeholders replaced + anchors ensured"))
                if write:
                    _write_json(paths["04"], d04)
    except Exception:
        pass

    # P2.6: persona suggested_traits in agent_profile.json (if present)
    try:
        ap = data.get("agent_profile")
        if isinstance(ap, dict):
            agent = ap.get("agent") if isinstance(ap.get("agent"), dict) else {}
            mbti = agent.get("mbti") if isinstance(agent.get("mbti"), dict) else {}
            code = _safe_str(mbti.get("mbti_code") or ap.get("persona") or agent.get("persona"))
            traits = mbti.get("suggested_traits") if isinstance(mbti.get("suggested_traits"), list) else []
            if code and (not traits or len(traits) < 3):
                source = "traits_engine"
                catalog_traits: List[str] = []
                if catalog_mbti:
                    match = next((e for e in catalog_mbti if (e.get("code") or "").upper() == code.upper()), None)
                    if isinstance(match, dict):
                        cand = match.get("suggested_traits")
                        if isinstance(cand, list):
                            catalog_traits = [str(item).strip() for item in cand if str(item).strip()]
                role_code = ""
                role_block = ap.get("role") if isinstance(ap.get("role"), dict) else {}
                if isinstance(role_block, dict):
                    role_code = _safe_str(role_block.get("code"))
                if not role_code:
                    agent_role = agent.get("role") if isinstance(agent.get("role"), dict) else {}
                    if isinstance(agent_role, dict):
                        role_code = _safe_str(agent_role.get("code") or agent_role.get("role_code"))
                identity_block = ap.get("identity") if isinstance(ap.get("identity"), dict) else {}
                agent_id = _safe_str((identity_block or {}).get("agent_id") or last_agent_id)
                traits = compose_traits(
                    lexicon=traits_lexicon,
                    overlays=traits_overlays,
                    mbti_traits=catalog_traits,
                    role_key=role_code or None,
                    axes=_mbti_axes(code),
                    agent_id=agent_id or None,
                )
                if not traits:
                    source = "fallback"
                    base_defaults = ["strategic_executor", "team_mobilizer", "process_anchor"]
                    traits = base_defaults[:]
                    while len(traits) < 3:
                        traits.append(base_defaults[len(traits) % len(base_defaults)])
                traits = traits[:5]
                mbti["suggested_traits"] = traits
                agent["mbti"] = mbti
                ap["agent"] = agent
                if "notes" in ap:
                    ap["notes"] = f"AUTOFIX {ts}: source={source}"
                pr.p2_fixed += 1
                pr.changes.append(("agent_profile.json", f"persona.suggested_traits -> {traits}"))
                if write:
                    _write_json(paths["agent_profile"], ap)
    except Exception:
        pass

    return pr


def run(root: str, write: bool) -> List[ProjectResult]:
    root_path = Path(root)
    # Load catalog mbti types for P2
    catalog_path = Path("src") / "persona" / "mbti_types.json"
    catalog_mbti = _read_json(catalog_path)
    lexicon_path = Path("src") / "persona" / "traits_lexicon.json"
    overlays_path = Path("src") / "persona" / "traits_overlays.json"
    traits_lexicon = _read_json(lexicon_path) or {}
    if not isinstance(traits_lexicon, Mapping):
        traits_lexicon = {}
    overlays_raw = _read_json(overlays_path) or {}
    traits_overlays: Dict[str, List[str]] = {}
    if isinstance(overlays_raw, Mapping):
        for key, values in overlays_raw.items():
            if not isinstance(values, Iterable) or isinstance(values, (str, bytes)):
                continue
            cleaned: List[str] = []
            for item in values:
                name = str(item).strip()
                if name:
                    cleaned.append(name)
            if cleaned:
                traits_overlays[str(key).upper()] = cleaned
    results: List[ProjectResult] = []
    for p in sorted([d for d in root_path.iterdir() if d.is_dir()]):
        results.append(
            _autofix_project(
                root_path,
                p,
                write=write,
                catalog_mbti=catalog_mbti,
                traits_lexicon=traits_lexicon,
                traits_overlays=traits_overlays,
            )
        )
    return results


def _print_summary(results: List[ProjectResult]) -> None:
    total_p0 = sum(r.p0_fixed for r in results)
    total_p1 = sum(r.p1_fixed for r in results)
    total_p2 = sum(r.p2_fixed for r in results)
    print(f"AUTOFIX SUMMARY: P0={total_p0} P1={total_p1} P2={total_p2}")
    for r in results:
        if r.changes:
            print(f"- {r.project}:")
            for f, desc in r.changes[:5]:
                print(f"  * {f}: {desc}")


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Autofix generated repo blanks")
    ap.add_argument("--root", default=WINDOWS_TARGET_ROOT)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    ns = ap.parse_args(argv)
    write = bool(ns.write) and not bool(ns.dry_run)
    results = run(ns.root, write=write)
    _print_summary(results)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
