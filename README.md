# Project_agent_NEO

Project NEO is a modular agentic AI scaffold designed for enterprise scenarios. The repository provides an opinionated yet
flexible foundation for building multi-skill agents that coordinate workflows, interact with business data sources, and
produce auditable reasoning trails.

## Features

- **Typed configuration** for agents, skills, and tools using Pydantic models.
- **Conversation memory** utilities that manage rolling chat history with optional reasoning traces.
- **Skill registry** with a simple abstraction for wiring custom capabilities into agents.
- **Agent and manager classes** that orchestrate planning, skill execution, and coordination across multiple agents.
- **Workflow runner** built on Rich for expressive terminal output.
- **Command line demo** showcasing how to configure and run an enterprise analyst agent.

## Getting started

### Installation

```bash
pip install -e .[dev]
```

### Run the demonstration agent

```bash
neo-agent "How can we improve Q3 pipeline conversion?"
```

The CLI will load a sample agent, propose an execution plan, run the configured skills, and output a reflection summarizing
recent context.

### Run the tests

```bash
pytest
```

## Project structure

```
src/neo_agent/
├── agents/          # Base agent and team manager implementations
├── cli.py           # CLI entry point wiring together a demo configuration
├── config.py        # Settings models for agents, skills, and tools
├── memory.py        # Conversation memory primitives
├── skills.py        # Skill abstractions and registry
└── workflow.py      # Simple Rich-powered workflow runner
```

Tests covering the configuration, memory, and agent flows live in `tests/`.

## Extending the scaffold

1. **Define new skills** by subclassing or instantiating `Skill` with custom handlers.
2. **Register tools** in `SkillSettings` to describe the external systems a skill uses.
3. **Customize planning** by overriding `BaseAgent.plan` to integrate LLMs or rule-based logic.
4. **Build multi-agent systems** by creating multiple `AgentSettings` and letting `AgentManager` coordinate them.

## License

MIT
