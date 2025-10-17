# Project NEO Agent

Project NEO Agent provides a lightweight, test-driven scaffold for experimenting with
agentic workflows. The repository intentionally limits itself to twenty files while
still covering configuration, planning, execution, and telemetry capabilities.

## Features

- **Deterministic configuration** – dataclass based models with JSON helpers keep
  runtime settings predictable.
- **Conversation aware state** – a structured conversation history is maintained for
  every dispatch, enabling downstream analysis.
- **Modular skills** – skills are simple callables that can be dynamically discovered
  from configuration entrypoints.
- **Planning pipeline** – the runtime produces a basic plan and executes each step
  through a configurable pipeline.
- **Observability** – event emission and telemetry utilities capture metrics during
  execution.

## Usage

```bash
pip install -e .[dev]
neo-agent --config path/to/config.json
```

If no configuration path is supplied, the default configuration containing the `echo`
skill will be used. Dispatches can be driven programmatically via the
`neo_agent.AgentRuntime` class:

```python
from neo_agent import AgentConfiguration, AgentRuntime

runtime = AgentRuntime(AgentConfiguration.default())
runtime.initialize()
result = runtime.dispatch({"input": "Ping"})
print(result["echo"])  # -> "Ping"
```

### Custom agent intake page

Launch the customizable intake experience using the bundled WSGI server to produce
tailored agent profiles and spec files:

```bash
python -m neo_agent.intake_app
```

Open http://127.0.0.1:5000/ to select the agent domain, role, toolsets, attributes,
and behavioral sliders. The form also accepts a LinkedIn profile URL; available
metadata is scraped and merged with the manual selections. Submitting the form
creates `agent_profile.json` alongside a `generated_specs/` directory containing the
derived configuration and metadata artifacts used by the generator.

#### Intake Section Order & Gating
- Order: Agent Profile → Business Context (NAICS + Domain) → Business Function & Role → Persona Alignment → Toolsets → Attributes → Preferences → LinkedIn → Custom Notes
- Generate Agent Repo is enabled only when: agent_name, NAICS, business_function, and role are all set.
- Persona Suggest is enabled after choosing a role.

## Testing

The repository relies on `pytest` for test execution:

```bash
pytest
```

## License

Project NEO Agent is released under the MIT License. See `LICENSE` for details.


### Run the intake app locally

To launch the intake form from a terminal on Windows, macOS, or Linux:

1. Install dependencies: ``pip install -e .[dev]``
2. Start the server (PowerShell or VS Code terminal): ``neo-agent serve --host 127.0.0.1 --port 5000``
3. Open http://127.0.0.1:5000/ in your browser. The server logs the health check and profile output paths.

Alternative entry points are also available if you prefer invoking Python directly:

- ``python -m neo_agent.intake_app``
- ``python -c "from neo_agent.intake_app import create_app; create_app().serve(host='127.0.0.1', port=5000)"``

Both commands respect the ``HOST`` and ``PORT`` environment variables, allowing you to override the bind address without changing code.

A quick smoke check after startup:

- ``curl http://127.0.0.1:5000/`` should return the intake HTML.
- ``curl http://127.0.0.1:5000/api/profile/validate -X POST -H "Content-Type: application/json" -d '{}'`` returns JSON containing ``status`` and ``issues`` fields.
