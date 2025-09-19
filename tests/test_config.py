from neo_agent.config import AgentSettings, MemorySettings, SkillSettings, ToolConfig


def test_agent_settings_validates_unique_skills():
    skill = SkillSettings(name="alpha", description="test")
    AgentSettings(name="A", role="Analyst", skills=[skill])


def test_skill_settings_validates_unique_tools():
    tool = ToolConfig(name="lookup", description="")
    SkillSettings(name="beta", description="", tools=[tool])


def test_memory_settings_defaults():
    settings = MemorySettings()
    assert settings.max_turns == 10
    assert settings.include_thoughts is True
