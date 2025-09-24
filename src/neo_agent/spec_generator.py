"""Utilities for generating agent specification files from intake profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from .configuration import AgentConfiguration, SkillConfiguration
from .exceptions import ConfigurationError
from .logging import get_logger

LOGGER = get_logger("spec_generator")


def _iter_skill_definitions(profile: Mapping[str, Any]) -> Iterable[SkillConfiguration]:
    """Yield :class:`SkillConfiguration` entries derived from ``profile`` selections."""

    toolset_section = profile.get("toolsets", {})
    selected = list(toolset_section.get("selected", []))
    custom = toolset_section.get("custom", [])
    if isinstance(custom, str):
        custom = [item.strip() for item in custom.split(",") if item.strip()]

    all_tools = []
    for source in (selected, custom):
        if isinstance(source, Iterable):
            for item in source:
                if not item:
                    continue
                all_tools.append(str(item))

    seen: set[str] = set()
    for tool in all_tools:
        normalized = tool.lower().replace(" ", "_")
        if normalized in seen:
            continue
        seen.add(normalized)
        description = f"Capability for {tool} sourced from intake selections"
        yield SkillConfiguration(
            name=normalized,
            description=description,
            entrypoint="neo_agent.skills:echo",
            parameters={"source_tool": tool},
        )


def _metadata_from_profile(profile: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the metadata payload merged into the agent configuration."""

    agent = profile.get("agent", {})
    preferences = profile.get("preferences", {})
    sliders = {
        "autonomy": preferences.get("autonomy"),
        "confidence": preferences.get("confidence"),
        "collaboration": preferences.get("collaboration"),
    }
    legacy_sliders = preferences.get("sliders") if isinstance(preferences, Mapping) else None
    if isinstance(legacy_sliders, Mapping):
        for key in ("autonomy", "confidence", "collaboration"):
            value = legacy_sliders.get(key)
            if value is not None:
                sliders[key] = value

    metadata: Dict[str, Any] = {
        "domain": agent.get("domain"),
        "role": agent.get("role"),
        "persona": agent.get("persona"),
        "toolsets": profile.get("toolsets", {}).get("selected", []),
        "custom_notes": profile.get("notes", ""),
        "sliders": sliders,
        "collaboration_mode": preferences.get("collab_mode")
        or preferences.get("collaboration_mode"),
        "communication_style": preferences.get("comm_style")
        or preferences.get("communication_style"),
        "linkedin": profile.get("linkedin", {}),
    }

    persona_section = profile.get("persona", {})
    if isinstance(persona_section, Mapping):
        mbti = persona_section.get("mbti")
        if mbti:
            metadata["mbti"] = mbti

    traits_section = profile.get("traits")
    traits = traits_section.get("traits") if isinstance(traits_section, Mapping) else None
    if isinstance(traits, Mapping):
        metadata["traits"] = dict(traits)
        provenance = traits_section.get("provenance")
        if provenance:
            metadata["traits_provenance"] = provenance

    prefs_knobs = preferences.get("prefs_knobs")
    if isinstance(prefs_knobs, Mapping):
        metadata["prefs_knobs"] = dict(prefs_knobs)

    return metadata


def build_agent_configuration(profile: Mapping[str, Any]) -> AgentConfiguration:
    """Construct an :class:`AgentConfiguration` from an intake ``profile`` payload."""

    agent_section = profile.get("agent", {})
    name = str(agent_section.get("name") or "Custom Project NEO Agent")
    version = str(agent_section.get("version") or "1.0.0")

    skills = tuple(_iter_skill_definitions(profile))

    if not skills:
        skills = (SkillConfiguration(
            name="echo",
            description="Fallback echo skill",
            entrypoint="neo_agent.skills:echo",
        ),)

    metadata = _metadata_from_profile(profile)

    return AgentConfiguration(
        name=name,
        version=version,
        skills=skills,
        metadata=metadata,
    )


def generate_agent_specs(profile: Mapping[str, Any], output_dir: Path) -> Dict[str, Path]:
    """Generate agent spec files in ``output_dir`` from the provided ``profile``."""

    if not isinstance(profile, Mapping):
        raise ConfigurationError("Profile must be a mapping of configuration fields")

    output_dir.mkdir(parents=True, exist_ok=True)

    configuration = build_agent_configuration(profile)

    config_path = output_dir / "agent_config.json"
    manifest_path = output_dir / "agent_manifest.json"
    metadata_path = output_dir / "agent_preferences.json"

    import json

    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(configuration.to_dict(), handle, indent=2)

    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(profile, handle, indent=2)

    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(configuration.metadata, handle, indent=2)

    LOGGER.info("Generated agent spec files in %s", output_dir)

    return {
        "agent_config": config_path,
        "agent_manifest": manifest_path,
        "agent_preferences": metadata_path,
    }


def generate_from_profile_path(profile_path: Path, output_dir: Path) -> Dict[str, Path]:
    """Load a profile from ``profile_path`` and write specs to ``output_dir``."""

    import json

    with profile_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, Mapping):
        raise ConfigurationError("Profile file must contain a JSON object")

    return generate_agent_specs(data, output_dir)

