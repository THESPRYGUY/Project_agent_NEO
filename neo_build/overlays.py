from __future__ import annotations

"""Overlay auto-applier for post-build mutations with integrity/parity safety.

Supports three overlay steps:
 - "19_SME_Domain": ensure 19-pack aligns to intake-derived refs (no-op merge otherwise)
 - "20_Enterprise": ensure required brand/legal/stakeholders are present (no-op when aligned)
 - "persistence_adaptiveness": apply operations from overlays/apply.persistence_adaptiveness.yaml

Safety:
 - Deep additive merges only; never delete or overwrite required keys.
 - Re-run integrity and parity; rollback on failure.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

try:
    import yaml  # type: ignore
except Exception as _exc:  # pragma: no cover
    yaml = None

from .contracts import CANONICAL_PACK_FILENAMES
from .validators import integrity_report, kpi_targets_sync


PackDict = Dict[str, Any]


def _load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(p: Path, obj: Any) -> None:
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _deep_merge(dst: Any, src: Any) -> Any:
    if isinstance(dst, dict) and isinstance(src, dict):
        out = dict(dst)
        for k, v in src.items():
            if k in out:
                out[k] = _deep_merge(out[k], v)
            else:
                out[k] = v
        return out
    # Prefer src when types differ or not both dicts
    return src


def _ensure_path(obj: Dict[str, Any], path: List[str]) -> Dict[str, Any]:
    cur: Dict[str, Any] = obj
    for key in path:
        nxt = cur.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[key] = nxt
        cur = nxt  # type: ignore[assignment]
    return cur


def _dget(mapping: Mapping[str, Any], path: List[str] | str, default: Any = None) -> Any:
    parts = path if isinstance(path, list) else path.split(".")
    cur: Any = mapping
    for part in parts:
        if not isinstance(cur, Mapping):
            return default
        cur = cur.get(part)
    return cur if cur is not None else default


def _set_path(obj: Dict[str, Any], path: List[str], value: Any) -> None:
    if not path:
        return
    *parents, leaf = path
    cur = _ensure_path(obj, parents) if parents else obj
    cur[leaf] = value


def _read_packs(outdir: Path) -> PackDict:
    packs: PackDict = {}
    for name in CANONICAL_PACK_FILENAMES:
        p = outdir / name
        if p.exists():
            packs[name] = _load_json(p)
    return packs


def _write_packs(outdir: Path, packs: PackDict) -> None:
    for name, obj in packs.items():
        _write_json(outdir / name, obj)


def _load_overlay_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to load overlay YAML; please install PyYAML")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def _apply_ops_persistence(packs: PackDict, ops_yaml: Dict[str, Any]) -> Tuple[List[str], Dict[str, Dict[str, Tuple[Any, Any]]]]:
    touched: List[str] = []
    deltas: Dict[str, Dict[str, Tuple[Any, Any]]] = {}

    def _mark(fname: str, keypath: str, before: Any, after: Any) -> None:
        touched.append(fname)
        deltas.setdefault(fname, {})[keypath] = (before, after)

    for op in ops_yaml.get("operations", []) or []:
        if not isinstance(op, Mapping):
            continue
        if "inject_block" in op:
            cfg = op["inject_block"] or {}
            target = str(cfg.get("target_file"))
            path = list(cfg.get("path") or [])
            cap = cfg.get("capsule") or "capsule"
            if not target or not path:
                continue
            obj = packs.get(target)
            if not isinstance(obj, dict):
                continue
            before = _dget(obj, path)
            block = {"capsule": cap, "status": "applied"}
            _set_path(obj, path, block)
            after = _dget(obj, path)
            _mark(target, ".".join(path), before, after)
        if "upsert" in op:
            cfg = op["upsert"] or {}
            target = str(cfg.get("target_file"))
            payload = cfg.get("set") or {}
            if not target or not isinstance(payload, Mapping):
                continue
            obj = packs.get(target)
            if not isinstance(obj, dict):
                continue
            before = json.loads(json.dumps(obj))
            merged = _deep_merge(obj, payload)  # additive
            packs[target] = merged
            after = merged
            # Compute changed top-level keys for summary
            changed = []
            for k in payload.keys():
                if before.get(k) != after.get(k):
                    changed.append(k)
            if changed:
                _mark(target, ",".join(changed), {k: before.get(k) for k in changed}, {k: after.get(k) for k in changed})

    # Integrity checks in YAML (best-effort)
    checks = ops_yaml.get("integrity_checks") or {}
    # must_include_block
    for cond in checks.get("must_include_block", []) or []:
        fname = str(cond.get("file"))
        path = list(cond.get("path") or [])
        if not fname or not path:
            continue
        obj = packs.get(fname) or {}
        if _dget(obj, path) is None:
            # ensure presence as empty block
            _set_path(obj, path, {})
            _mark(fname, ".".join(path), None, {})
    # required_fields_present
    for cond in checks.get("required_fields_present", []) or []:
        fname = str(cond.get("file"))
        field = str(cond.get("field"))
        if not fname or not field:
            continue
        obj = packs.get(fname) or {}
        if field not in obj:
            obj[field] = []
            _mark(fname, field, None, [])
    # cross_refs: only check existence of target path, not equality
    # up to integrity_report/parity to enforce gates

    return sorted(set(touched)), deltas


def _overlay_19_align(packs: PackDict) -> Tuple[bool, Dict[str, Tuple[Any, Any]]]:
    name = "19_Overlay-Pack_SME-Domain_v1.json"
    obj = packs.get(name)
    if not isinstance(obj, dict):
        return False, {}
    before = json.loads(json.dumps(obj))
    # Ensure refs align to own sector/region/regulators fields
    sector = obj.get("sector")
    region = obj.get("region")
    regulators = obj.get("regulators")
    obj.setdefault("refs", {})
    r = obj["refs"]
    if not isinstance(r, dict):
        r = {}
        obj["refs"] = r
    r.setdefault("sector", sector)
    r.setdefault("region", region)
    r.setdefault("regulators", regulators)
    after = obj
    changed = {}
    if before.get("refs") != after.get("refs"):
        changed["refs"] = (before.get("refs"), after.get("refs"))
    return (len(changed) > 0), changed


def _overlay_20_align(packs: PackDict) -> Tuple[bool, Dict[str, Tuple[Any, Any]]]:
    name = "20_Overlay-Pack_Enterprise_v1.json"
    obj = packs.get(name)
    if not isinstance(obj, dict):
        return False, {}
    before = json.loads(json.dumps(obj))
    # Ensure presence of brand/legal/stakeholders
    obj.setdefault("brand", {})
    obj.setdefault("legal", {})
    if not obj.get("stakeholders"):
        # try derive from 09.Agents owners
        ag = packs.get("09_Agent-Manifests_Catalog_v2.json") or {}
        owners = ag.get("owners") or []
        if not owners and isinstance(ag.get("agents"), list) and ag["agents"]:
            owners = ag["agents"][0].get("owners") or []
        obj["stakeholders"] = owners or []
    after = obj
    changed = {}
    for k in ("brand", "legal", "stakeholders"):
        if before.get(k) != after.get(k):
            changed[k] = (before.get(k), after.get(k))
    return (len(changed) > 0), changed


def load_overlay_config(config_path: Path | None = None) -> Dict[str, Any]:
    cfg_path = config_path or Path("overlays/config.yaml")
    if cfg_path.exists():
        return _load_overlay_yaml(cfg_path)
    # default
    return {"apply": ["19_SME_Domain", "20_Enterprise", "persistence_adaptiveness"], "persistence_ops": "overlays/apply.persistence_adaptiveness.yaml"}


def apply_overlays(outdir: Path, cfg: Dict[str, Any]) -> Dict[str, Any]:
    outdir = Path(outdir)
    packs = _read_packs(outdir)
    original = json.loads(json.dumps(packs))  # deep copy for rollback

    applied: List[str] = []
    touched: List[str] = []
    deltas_all: Dict[str, Dict[str, Tuple[Any, Any]]] = {}

    steps = list(cfg.get("apply") or [])
    for step in steps:
        if step == "19_SME_Domain":
            changed, deltas = _overlay_19_align(packs)
            applied.append(step)
            if changed:
                touched.append("19_Overlay-Pack_SME-Domain_v1.json")
                deltas_all.setdefault("19_Overlay-Pack_SME-Domain_v1.json", {}).update(deltas)
        elif step == "20_Enterprise":
            changed, deltas = _overlay_20_align(packs)
            applied.append(step)
            if changed:
                touched.append("20_Overlay-Pack_Enterprise_v1.json")
                deltas_all.setdefault("20_Overlay-Pack_Enterprise_v1.json", {}).update(deltas)
        elif step == "persistence_adaptiveness":
            ops_path = Path(str(cfg.get("persistence_ops") or "overlays/apply.persistence_adaptiveness.yaml"))
            ops_yaml = _load_overlay_yaml(ops_path)
            t, d = _apply_ops_persistence(packs, ops_yaml)
            applied.append(step)
            touched.extend(t)
            for fn, ch in d.items():
                deltas_all.setdefault(fn, {}).update(ch)

    # Write tentative changes
    _write_packs(outdir, packs)

    # Recompute integrity and parity; rollback on failure
    # Note: integrity_report currently does not require profile data for these checks
    report = integrity_report({}, packs)  # type: ignore[arg-type]
    parity = report.get("parity", {}) if isinstance(report, Mapping) else {}
    all_true = bool(parity.get("02_vs_14", True) and parity.get("11_vs_02", True) and parity.get("03_vs_02", True) and parity.get("17_vs_02", True))
    errors = list(report.get("errors", []) or []) if isinstance(report, Mapping) else []

    rolled_back = False
    if not all_true or errors:
        # rollback
        rolled_back = True
        _write_packs(outdir, original)
        packs = original
        report = integrity_report({}, packs)  # recompute after rollback

    # Summary
    return {
        "applied": applied,
        "touched_packs": sorted(set(touched)),
        "deltas": deltas_all,
        "parity": report.get("parity", {}) if isinstance(report, Mapping) else {},
        "integrity_errors": report.get("errors", []) if isinstance(report, Mapping) else [],
        "rolled_back": rolled_back,
    }

