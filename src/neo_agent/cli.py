"""Command line entry point for the Project NEO scaffold."""
from __future__ import annotations

import argparse
from typing import Dict

from rich.console import Console

from .agents.manager import AgentManager
from .config import AgentSettings, MemorySettings, SkillSettings, ToolConfig
from .skills import Skill


def build_default_skill(skill_settings: SkillSettings) -> Skill:
    """Create a trivial skill implementation for demonstration purposes."""

    def handler(context, inputs: Dict[str, str]) -> str:
        context.log(f"[italic]Running skill[/] {skill_settings.name} with inputs {inputs}")
        topic = inputs.get("topic", "general task")
        return f"Skill {skill_settings.name} responded to {topic}: {skill_settings.description}"

    return Skill(
        name=skill_settings.name,
        description=skill_settings.description,
        handler=handler,
        settings=skill_settings,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a demonstration agent workflow")
    parser.add_argument("query", help="Business problem for the agent to solve")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    console = Console()

    sales_skill = SkillSettings(
        name="sales_insight",
        description="Provide sales pipeline recommendations",
        inputs=["topic"],
        outputs=["analysis"],
        tools=[ToolConfig(name="crm_lookup", description="Query CRM records")],
    )
    research_skill = SkillSettings(
        name="market_research",
        description="Summarize market intelligence for the query",
        inputs=["topic"],
        outputs=["summary"],
    )

    agent_settings = AgentSettings(
        name="Athena",
        role="Enterprise Strategy Analyst",
        goals=["Deliver actionable intelligence", "Coordinate cross-functional insights"],
        memory=MemorySettings(max_turns=5),
        skills=[sales_skill, research_skill],
    )

    manager = AgentManager(console=console)
    agent = manager.create_agent(agent_settings, build_default_skill)

    plan = agent.plan(args.query)
    console.rule("[bold green]Execution Plan")
    for step in plan:
        console.print(f"- {step}")

    for skill_name in plan:
        output = agent.act(skill_name, {"topic": args.query})
        console.print(f"[bold]{skill_name}[/] -> {output}")

    console.rule("[bold green]Reflection")
    console.print(agent.reflect())


if __name__ == "__main__":  # pragma: no cover
    main()
