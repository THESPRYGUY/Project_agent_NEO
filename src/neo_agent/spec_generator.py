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


def _extract_persona_metadata(profile: Mapping[str, Any]) -> Dict[str, Any] | None:
    def _coerce(candidate: Any) -> Dict[str, Any] | None:
        if not isinstance(candidate, Mapping):
            return None
        code = candidate.get("mbti_code") or candidate.get("code")
        if not code:
            return None
        axes_source = candidate.get("axes")
        axes = dict(axes_source) if isinstance(axes_source, Mapping) else {}
        traits_source = candidate.get("suggested_traits", [])
        traits: list[Any] = []
        if isinstance(traits_source, Iterable) and not isinstance(
            traits_source, (str, bytes)
        ):
            for item in traits_source:
                if isinstance(item, Mapping):
                    traits.append(dict(item))
                else:
                    traits.append({"name": str(item)})
        return {
            "mbti_code": str(code).upper(),
            "name": str(candidate.get("name") or candidate.get("nickname") or ""),
            "description": str(
                candidate.get("description") or candidate.get("summary") or ""
            ),
            "axes": axes,
            "suggested_traits": traits,
        }

    persona_section = profile.get("persona")
    if isinstance(persona_section, Mapping):
        meta = _coerce(persona_section.get("persona_details"))
        if meta:
            return meta
        agent_section = persona_section.get("agent")
        if isinstance(agent_section, Mapping):
            meta = _coerce(agent_section.get("mbti"))
            if meta:
                return meta

    agent_section = profile.get("agent")
    if isinstance(agent_section, Mapping):
        meta = _coerce(agent_section.get("mbti"))
        if meta:
            return meta

    fallback = profile.get("persona_details")
    return _coerce(fallback)


def _metadata_from_profile(profile: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the metadata payload merged into the agent configuration."""

    agent = profile.get("agent", {})
    preferences = profile.get("preferences", {})
    sliders = preferences.get("sliders", {})

    attributes = profile.get("attributes", {})
    selected_attributes = attributes.get("selected", [])

    metadata: Dict[str, Any] = {
        "domain": agent.get("domain"),
        "role": agent.get("role"),
        "toolsets": profile.get("toolsets", {}).get("selected", []),
        "attributes": selected_attributes,
        "custom_notes": profile.get("notes", ""),
        "sliders": sliders,
        "collaboration_mode": preferences.get("collaboration_mode"),
        "communication_style": preferences.get("communication_style"),
        "linkedin": profile.get("linkedin", {}),
    }

    persona_metadata = _extract_persona_metadata(profile)
    metadata["persona"] = (
        persona_metadata if persona_metadata is not None else agent.get("persona")
    )

    return metadata


def build_agent_configuration(profile: Mapping[str, Any]) -> AgentConfiguration:
    """Construct an :class:`AgentConfiguration` from an intake ``profile`` payload."""

    agent_section = profile.get("agent", {})
    name = str(agent_section.get("name") or "Custom Project NEO Agent")
    version = str(agent_section.get("version") or "1.0.0")

    skills = tuple(_iter_skill_definitions(profile))

    if not skills:
        skills = (
            SkillConfiguration(
                name="echo",
                description="Fallback echo skill",
                entrypoint="neo_agent.skills:echo",
            ),
        )

    metadata = _metadata_from_profile(profile)

    return AgentConfiguration(
        name=name,
        version=version,
        skills=skills,
        metadata=metadata,
    )


def generate_agent_specs(
    profile: Mapping[str, Any], output_dir: Path
) -> Dict[str, Path]:
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
