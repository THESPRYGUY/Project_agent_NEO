"""Repository build orchestration for Project NEO agent packs."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple
from uuid import NAMESPACE_URL, uuid5

from .errors import SchemaValidationError, TemplateRenderError
from .manifest import make_manifest
from .packaging import ensure_directory, git_init, package_zip
from .validators import validate_build_options, validate_profile

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = PROJECT_ROOT / "templates"
PACK_DIR = TEMPLATE_DIR / "pack_v2"
OUTPUT_ROOT = PROJECT_ROOT / "generated"

PACK_FILENAMES = [
    "01_README+Directory-Map_v2.json",
    "02_Global-Instructions_v2.json",
    "03_Operating-Rules_v2.json",
    "04_Governance+Risk-Register_v2.json",
    "05_Safety+Privacy_Guardrails_v2.json",
    "06_Role-Recipes_Index_v2.json",
    "07_Subagent_Role-Recipes_v2.json",
    "08_Memory-Schema_v2.json",
    "09_Agent-Manifests_Catalog_v2.json",
    "10_Prompt-Pack_v2.json",
    "11_Workflow-Pack_v2.json",
    "12_Tool+Data-Registry_v2.json",
    "13_Knowledge-Graph+RAG_Config_v2.json",
    "14_KPI+Evaluation-Framework_v2.json",
    "15_Observability+Telemetry_Spec_v2.json",
    "16_Reasoning-Footprints_Schema_v1.json",
    "17_Lifecycle-Pack_v2.json",
    "18_Reporting-Pack_v2.json",
    "19_Overlay-Pack_SME-Domain_v1.json",
    "20_Overlay-Pack_Enterprise_v1.json",
]


def _slugify(value: str) -> str:
    filtered = [ch.lower() if ch.isalnum() else "-" for ch in value]
    slug = "".join(filtered).strip("-")
    slug = "-".join(part for part in slug.split("-") if part)
    return slug or "agent"


def _canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _pretty_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, indent=2)


def _load_template(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:  # pragma: no cover - defensive guard
        raise TemplateRenderError("E_TEMPLATE_RENDER", f"Template missing: {path}") from exc


def _render_template(raw: str, context: Mapping[str, Any]) -> str:
    def replace_placeholder(token: str) -> str:
        if token not in context:
            raise TemplateRenderError("E_TEMPLATE_RENDER", f"Missing template key: {token}")
        return str(context[token])

    rendered = []
    idx = 0
    while idx < len(raw):
        start = raw.find("{{", idx)
        if start == -1:
            rendered.append(raw[idx:])
            break
        rendered.append(raw[idx:start])
        end = raw.find("}}", start)
        if end == -1:
            raise TemplateRenderError("E_TEMPLATE_RENDER", "Unclosed placeholder")
        token = raw[start + 2 : end].strip()
        rendered.append(replace_placeholder(token))
        idx = end + 2
    return "".join(rendered)


def _build_context(profile: Mapping[str, Any], options: Mapping[str, Any]) -> Dict[str, Any]:
    canonical_inputs = {
        "profile": json.loads(_canonical_json(profile)),
        "options": json.loads(_canonical_json(options)),
    }
    canonical_blob = _canonical_json(canonical_inputs)
    inputs_sha = hashlib.sha256(canonical_blob.encode("utf-8")).hexdigest()
    profile_id = str(uuid5(NAMESPACE_URL, inputs_sha))
    seed_seconds = int(inputs_sha[:12], 16) % (60 * 60 * 24 * 365)
    generated_at = datetime.fromtimestamp(seed_seconds, tz=timezone.utc).isoformat()

    persona = profile.get("persona", {})
    domain = profile.get("domain", {})
    domain_naics = domain.get("naics") if isinstance(domain, Mapping) else None
    industry = profile.get("industry") or {"naics": domain_naics}
    toolsets = profile.get("toolsets", {})
    traits = profile.get("traits", {})
    preferences = profile.get("preferences", {})

    highlights = {
        "capabilities": toolsets.get("capabilities", []),
        "connectors": toolsets.get("connectors", []),
        "ops": toolsets.get("ops", {}),
        "governance": toolsets.get("governance", {}),
        "naics": domain.get("naics") or industry.get("naics"),
    }

    pack_listing_text = "\n".join(f"- {name}" for name in PACK_FILENAMES)

    context = {
        "generated_at": generated_at,
        "profile_id": profile_id,
        "inputs_sha256": inputs_sha,
        "classification": "confidential",
        "disclaimer": "Outputs are generated offline; review before distribution.",
        "persona_json": _pretty_json(persona),
        "domain_json": _pretty_json(domain),
        "industry_json": _pretty_json(industry),
        "toolsets_json": _pretty_json(toolsets),
        "traits_json": _pretty_json(traits),
        "preferences_json": _pretty_json(preferences),
        "highlights_json": _pretty_json(highlights),
        "pack_listing_text": pack_listing_text,
        "pack_listing": _pretty_json(PACK_FILENAMES),
    }
    return context


def _collect_outputs(context: Mapping[str, Any]) -> List[Tuple[str, bytes]]:
    outputs: List[Tuple[str, bytes]] = []
    for name in PACK_FILENAMES:
        template_path = PACK_DIR / f"{name}.tmpl"
        rendered = _render_template(_load_template(template_path), context)
        outputs.append((name, rendered.encode("utf-8")))
    readme_template = _load_template(TEMPLATE_DIR / "README_intro.md.tmpl")
    readme_rendered = _render_template(readme_template, context)
    outputs.append(("README_intro.md", readme_rendered.encode("utf-8")))
    return outputs


def _render_manifest(context: Mapping[str, Any], outputs: Iterable[Tuple[str, bytes]]) -> bytes:
    manifest_dict = make_manifest(context, [(Path(name), content) for name, content in outputs])
    return json.dumps(manifest_dict, indent=2).encode("utf-8")


def _plan_actions(repo_dir: Path, outputs: Iterable[Tuple[str, bytes]], overwrite: str) -> List[Dict[str, Any]]:
    plan: List[Dict[str, Any]] = []
    for name, content in outputs:
        target = repo_dir / name
        sha_new = hashlib.sha256(content).hexdigest()
        if target.exists():
            existing = target.read_bytes()
            sha_old = hashlib.sha256(existing).hexdigest()
            if sha_old == sha_new:
                action = "skip"
            else:
                if overwrite == "abort":
                    raise SchemaValidationError("E_SCHEMA_INVALID_OPTIONS", f"Existing file differs: {name}")
                action = "update"
        else:
            action = "create"
        plan.append({"path": name, "action": action, "sha256_after": sha_new})
    return plan


def plan_repository(profile: Mapping[str, Any], options: Mapping[str, Any], *, output_root: Path | None = None) -> Dict[str, Any]:
    output_root = output_root or OUTPUT_ROOT
    issues = validate_profile(profile)
    if issues:
        raise SchemaValidationError("E_SCHEMA_INVALID_PROFILE", "Profile validation failed")
    option_issues = validate_build_options(options)
    if option_issues:
        raise SchemaValidationError("E_SCHEMA_INVALID_OPTIONS", "Build options validation failed")
    context = _build_context(profile, options)
    repo_slug = _slugify(str(profile.get("persona", {}).get("name", "neo-agent")))
    repo_dir = output_root / f"neo_agent_{repo_slug}"
    outputs = _collect_outputs(context)
    manifest_bytes = _render_manifest(context, outputs)
    outputs_with_manifest = outputs + [("manifest.json", manifest_bytes)]
    plan = _plan_actions(repo_dir, outputs_with_manifest, str(options.get("overwrite", "safe")))
    return {
        "status": "ok",
        "plan": {"files": plan, "inputs_sha256": context["inputs_sha256"]},
        "context": context,
        "repo_dir": repo_dir,
        "outputs": outputs,
        "manifest": manifest_bytes,
    }


def build_repository(profile: Mapping[str, Any], options: Mapping[str, Any], *, output_root: Path | None = None) -> Dict[str, Any]:
    result = plan_repository(profile, options, output_root=output_root)
    context = result["context"]
    repo_dir: Path = result["repo_dir"]
    outputs: List[Tuple[str, bytes]] = result["outputs"]
    manifest_bytes: bytes = result["manifest"]
    ensure_directory(repo_dir)
    overwrite = str(options.get("overwrite", "safe"))
    for name, content in outputs + [("manifest.json", manifest_bytes)]:
        target = repo_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() == hashlib.sha256(content).hexdigest():
                continue
            if overwrite == "abort":
                raise SchemaValidationError("E_SCHEMA_INVALID_OPTIONS", f"Existing file differs: {name}")
        with target.open("wb") as handle:
            handle.write(content)
    if options.get("git_init"):
        git_init(repo_dir)
    zip_path = None
    if options.get("zip", True):
        zip_path = package_zip(repo_dir, repo_dir.with_suffix(".zip"))
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    result_payload = {
        "status": "ok",
        "repo_path": str(repo_dir),
        "zip_path": str(zip_path) if zip_path else None,
        "manifest": manifest,
        "timings_ms": {
            "validate": 0,
            "render": 0,
            "package": 0,
        },
    }
    return result_payload
