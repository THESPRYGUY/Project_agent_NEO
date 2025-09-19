"""Configuration models for the Project NEO agent runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping

from .exceptions import ConfigurationError


@dataclass(slots=True)
class SkillConfiguration:
    """Definition of a skill that the runtime can execute."""

    name: str
    description: str
    entrypoint: str
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the skill configuration to a JSON compatible mapping."""

        return {
            "name": self.name,
            "description": self.description,
            "entrypoint": self.entrypoint,
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SkillConfiguration":
        """Deserialize a :class:`SkillConfiguration` from ``payload``."""

        missing = [key for key in ("name", "description", "entrypoint") if key not in payload]
        if missing:
            raise ConfigurationError(f"Missing keys for skill configuration: {missing}")

        return cls(
            name=str(payload["name"]),
            description=str(payload["description"]),
            entrypoint=str(payload["entrypoint"]),
            parameters=dict(payload.get("parameters", {})),
        )


@dataclass(slots=True)
class AgentConfiguration:
    """Top level configuration object for the runtime."""

    name: str
    version: str
    skills: Iterable[SkillConfiguration] = field(default_factory=tuple)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.skills = tuple(self.skills)
        self.metadata = dict(self.metadata)

    def skill_map(self) -> Dict[str, SkillConfiguration]:
        """Return the skills keyed by their name."""

        return {skill.name: skill for skill in self.skills}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize configuration to a JSON compatible structure."""

        return {
            "name": self.name,
            "version": self.version,
            "skills": [skill.to_dict() for skill in self.skills],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AgentConfiguration":
        """Deserialize an :class:`AgentConfiguration` from ``payload``."""

        for key in ("name", "version"):
            if key not in payload:
                raise ConfigurationError(f"Missing configuration key: {key}")

        skills_payload = payload.get("skills", [])
        if not isinstance(skills_payload, Iterable):
            raise ConfigurationError("Skills must be an iterable")

        skills = tuple(SkillConfiguration.from_dict(item) for item in skills_payload)

        return cls(
            name=str(payload["name"]),
            version=str(payload["version"]),
            skills=skills,
            metadata=dict(payload.get("metadata", {})),
        )

    @classmethod
    def from_path(cls, path: Path) -> "AgentConfiguration":
        """Load configuration from a JSON file at ``path``."""

        import json

        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, MutableMapping):
            raise ConfigurationError("Configuration file must contain a JSON object")
        return cls.from_dict(data)

    @classmethod
    def default(cls) -> "AgentConfiguration":
        """Return a simple default configuration used for smoke testing."""

        return cls(
            name="Project NEO Agent",
            version="0.1.0",
            skills=(
                SkillConfiguration(
                    name="echo",
                    description="Echo the input payload for debugging",
                    entrypoint="neo_agent.skills:echo",
                ),
            ),
            metadata={"environment": "development"},
        )


def merge_metadata(*sources: Mapping[str, Any]) -> Dict[str, Any]:
    """Merge metadata dictionaries with the latter taking precedence."""

    result: Dict[str, Any] = {}
    for source in sources:
        result.update(source)
    return result
