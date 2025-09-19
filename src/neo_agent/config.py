"""Configuration models for NEO agents."""
from __future__ import annotations

from functools import cached_property
from typing import Any, Dict, Iterable, List

from pydantic import BaseModel, Field, model_validator


class ToolConfig(BaseModel):
    """Configuration for an external tool the agent can call."""

    name: str = Field(..., description="Unique tool name")
    description: str = Field(..., description="High level description of what the tool does")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Schema-like parameter description")
    requires_confirmation: bool = Field(
        default=False,
        description="Whether the agent should confirm with a human before invoking the tool.",
    )


class SkillSettings(BaseModel):
    """Settings that describe a skill's capabilities and constraints."""

    name: str
    description: str
    inputs: List[str] = Field(default_factory=list, description="Inputs required to execute the skill")
    outputs: List[str] = Field(default_factory=list, description="Outputs the skill produces")
    tools: List[ToolConfig] = Field(default_factory=list, description="Tools the skill can leverage")

    @model_validator(mode="after")
    def validate_unique_tool_names(self) -> "SkillSettings":
        names = [tool.name for tool in self.tools]
        if len(names) != len(set(names)):
            raise ValueError("Skill tools must have unique names")
        return self


class MemorySettings(BaseModel):
    """Settings for how the agent stores interaction history."""

    max_turns: int = Field(default=10, ge=1, description="Maximum number of conversation turns to keep in memory")
    include_thoughts: bool = Field(
        default=True,
        description="If True internal reasoning traces are included in memory snapshots.",
    )


class AgentSettings(BaseModel):
    """High level configuration for an agent."""

    name: str
    role: str
    goals: List[str] = Field(default_factory=list)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    skills: List[SkillSettings] = Field(default_factory=list)
    traits: Dict[str, Any] = Field(default_factory=dict)

    @cached_property
    def skill_map(self) -> Dict[str, SkillSettings]:
        """Convenience lookup of skills by name."""

        return {skill.name: skill for skill in self.skills}

    def skill_descriptions(self) -> Iterable[str]:
        """Return formatted skill descriptions suitable for prompts."""

        for skill in self.skills:
            tool_summary = ", ".join(tool.name for tool in skill.tools) or "no tools"
            yield f"{skill.name}: {skill.description} (tools: {tool_summary})"

    @model_validator(mode="after")
    def validate_unique_skills(self) -> "AgentSettings":
        names = [skill.name for skill in self.skills]
        if len(names) != len(set(names)):
            raise ValueError("Agent skills must have unique names")
        return self


def build_settings_from_dict(raw: Dict[str, Any]) -> AgentSettings:
    """Utility helper to build :class:`AgentSettings` from a plain dictionary."""

    return AgentSettings.model_validate(raw)


__all__ = [
    "AgentSettings",
    "MemorySettings",
    "SkillSettings",
    "ToolConfig",
    "build_settings_from_dict",
]
