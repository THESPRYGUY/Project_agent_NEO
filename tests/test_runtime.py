from __future__ import annotations

from neo_agent.configuration import AgentConfiguration, SkillConfiguration
from neo_agent.runtime import AgentRuntime


def test_runtime_executes_custom_skill() -> None:
    configuration = AgentConfiguration(
        name="Test Agent",
        version="1.0.0",
        skills=[
            SkillConfiguration(
                name="greet",
                description="Greets the user",
                entrypoint="neo_agent.skills:greet",
            )
        ],
    )
    runtime = AgentRuntime(configuration)
    runtime.initialize()

    result = runtime.dispatch({"input": "Neo"})

    assert result["greeting"] == "Hello Neo"
    assert "greet" in runtime.state.completed_skills


def test_runtime_records_messages() -> None:
    configuration = AgentConfiguration.default()
    runtime = AgentRuntime(configuration)
    runtime.initialize()
    runtime.dispatch({"input": "Ping"})

    history = runtime.state.history()
    assert any(message.content == "Executed echo" for message in history)
