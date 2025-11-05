from __future__ import annotations

import json
from pathlib import Path

import pytest

from neo_agent.configuration import (
    AgentConfiguration,
    ConfigurationError,
    SkillConfiguration,
    merge_metadata,
)


def test_agent_configuration_round_trip(tmp_path: Path) -> None:
    configuration = AgentConfiguration.default()
    path = tmp_path / "config.json"
    path.write_text(json.dumps(configuration.to_dict()))

    loaded = AgentConfiguration.from_path(path)
    assert loaded.name == configuration.name
    assert loaded.version == configuration.version
    assert [skill.name for skill in loaded.skills] == ["echo"]


def test_missing_skill_key() -> None:
    with pytest.raises(ConfigurationError):
        SkillConfiguration.from_dict({"name": "broken"})


def test_merge_metadata() -> None:
    result = merge_metadata({"a": 1}, {"b": 2}, {"a": 3})
    assert result == {"a": 3, "b": 2}
