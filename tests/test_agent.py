from neo_agent.agents.base import BaseAgent
from neo_agent.config import AgentSettings, MemorySettings, SkillSettings
from neo_agent.skills import Skill


def make_skill(setting: SkillSettings) -> Skill:
    def handler(context, inputs):
        return f"handled {setting.name}"

    return Skill(name=setting.name, description=setting.description, handler=handler, settings=setting)


def build_agent() -> BaseAgent:
    settings = AgentSettings(
        name="Test",
        role="Tester",
        memory=MemorySettings(max_turns=3),
        skills=[
            SkillSettings(name="alpha", description="alpha skill"),
            SkillSettings(name="beta", description="beta skill"),
        ],
    )
    agent = BaseAgent(settings=settings)
    agent.load_skills(make_skill)
    return agent


def test_agent_plan_returns_skills():
    agent = build_agent()
    plan = agent.plan("alpha mission")
    assert "alpha" in plan


def test_agent_act_records_memory():
    agent = build_agent()
    agent.act("alpha", {})
    assert len(agent.memory_context()) == 1


def test_agent_reflect_contains_entries():
    agent = build_agent()
    agent.observe("user", "hello")
    agent.observe("agent", "hi")
    reflection = agent.reflect()
    assert "hello" in reflection
    assert "hi" in reflection
