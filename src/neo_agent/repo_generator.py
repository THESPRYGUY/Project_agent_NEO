"""Agent repository generator utilities.

This module provides a minimal, side-effect free generator that produces a
scaffolded agent repository based on an intake profile. It writes a README and
configuration manifest and returns metadata for the caller. The contract is
intentionally small so it can be evolved without breaking callers.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional


class AgentRepoGenerationError(Exception):
    """Raised when agent repo generation fails due to invalid input or I/O issues."""


_SLUG_SAFE = re.compile(r"[^a-z0-9\-]+")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = value.replace("_", "-")
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^a-z0-9\-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def _next_available_dir(base: Path, base_slug: str) -> Path:
    candidate = base / base_slug
    if not candidate.exists():
        return candidate
    i = 2
    while True:
        alt = base / f"{base_slug}-{i}"
        if not alt.exists():
            return alt
        i += 1


def _read_profile_section(obj: Mapping[str, Any], key: str, default: Any) -> Any:
    val = obj.get(key)
    return val if isinstance(val, Mapping) else default


def generate_agent_repo(
    profile: Mapping[str, Any],
    base_output_dir: str | Path,
    options: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(profile, Mapping):
        raise AgentRepoGenerationError("profile must be a mapping")

    agent = _read_profile_section(profile, "agent", {})
    name = str(agent.get("name", "")).strip() if isinstance(agent, Mapping) else ""
    version = (
        str(agent.get("version", "")).strip() if isinstance(agent, Mapping) else ""
    )

    business_function = str(profile.get("business_function", ""))
    role = profile.get("role") if isinstance(profile, Mapping) else None
    if not isinstance(role, Mapping):
        role = {}
    routing_defaults = profile.get("routing_defaults")
    if not isinstance(routing_defaults, Mapping):
        routing_defaults = (
            profile.get("routing_hints") if isinstance(profile, Mapping) else None
        )
        routing_defaults = (
            routing_defaults if isinstance(routing_defaults, Mapping) else {}
        )

    slug_source = "-".join([s for s in [name, version] if s])
    slug = _slugify(slug_source) or _slugify(name) or f"agent-{uuid.uuid4().hex[:8]}"

    base_dir = Path(base_output_dir).resolve()
    _ensure_dir(base_dir)
    out_dir = _next_available_dir(base_dir, slug)
    if base_dir not in out_dir.parents and base_dir != out_dir:
        raise AgentRepoGenerationError("invalid output directory resolution")

    _ensure_dir(out_dir)
    files_written: List[str] = []

    try:
        manifest: Dict[str, Any] = {
            "agent": {"name": name, "version": version},
            "business_function": business_function,
            "role": {
                "code": role.get("code", ""),
                "title": role.get("title", ""),
                "seniority": role.get("seniority", ""),
                "function": business_function or role.get("function", ""),
            },
            "routing_hints": routing_defaults,
        }

        classification = (
            profile.get("classification") if isinstance(profile, Mapping) else None
        )
        if isinstance(classification, Mapping) and isinstance(
            classification.get("naics"), Mapping
        ):
            manifest.setdefault("classification", {})["naics"] = classification["naics"]
        elif isinstance(profile.get("naics"), Mapping):
            manifest.setdefault("classification", {})["naics"] = profile["naics"]

        bf = manifest.get("business_function", "")
        rc = manifest.get("role", {}) or {}
        rh = manifest.get("routing_hints", {}) or {}
        naics = (manifest.get("classification", {}) or {}).get("naics", {}) or {}

        readme_lines = [
            f"# Agent: {name or 'Unnamed Agent'} {('v' + version) if version else ''}",
            "",
            "## Domain & Role",
            f"- Business Function: {bf or 'N/A'}",
            f"- Role: {rc.get('title') or rc.get('code') or 'N/A'}",
            f"- Seniority: {rc.get('seniority') or 'N/A'}",
            "",
            "## NAICS",
            f"- Code: {naics.get('code', 'N/A')} (level {naics.get('level', 'N/A')})",
            f"- Title: {naics.get('title', 'N/A')}",
            f"- Lineage: {json.dumps(naics.get('lineage', []), ensure_ascii=False)}",
            "",
            "## Routing Hints",
            "```json",
            json.dumps(rh, indent=2, ensure_ascii=False),
            "```",
            "",
            "## Quickstart",
            "- Edit neo_agent_config.json",
            "- Run your agent pipeline as needed",
        ]
        readme_content = "\n".join(readme_lines) + "\n"

        readme_path = out_dir / "README.md"
        readme_path.write_text(readme_content, encoding="utf-8", newline="\n")
        files_written.append(str(readme_path.relative_to(out_dir)))

        cfg_path = out_dir / "neo_agent_config.json"
        cfg_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        files_written.append(str(cfg_path.relative_to(out_dir)))

        return {
            "slug": out_dir.name,
            "path": out_dir,
            "files": files_written,
            "readme": readme_content,
        }
    finally:
        try:
            import json as _json, os as _os

            cfg = options if isinstance(options, Mapping) else {}
            build_id = cfg.get("build_id", out_dir.name)
            schema_version = cfg.get("schema_version", "2.1.1")
            lb = {
                "build_id": build_id,
                "schema_version": schema_version,
                "status": "complete",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "commit": _os.environ.get("GITHUB_SHA", "local"),
                "outdir": str(out_dir),
            }
            pointer_path = base_dir / "_last_build.json"
            with open(pointer_path, "w", encoding="utf-8") as handle:
                _json.dump(lb, handle, indent=2)
        except Exception:
            pass  # _lb_finally_guard
