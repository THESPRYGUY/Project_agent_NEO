"""Command line interface for running Project NEO agents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .configuration import AgentConfiguration
from .runtime import AgentRuntime


def load_configuration(path: Path | None) -> AgentConfiguration:
    """Load an :class:`AgentConfiguration` from ``path`` or return the default."""

    if path is None:
        return AgentConfiguration.default()

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data: Dict[str, Any] = json.load(handle)

    return AgentConfiguration.from_dict(data)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point used by ``python -m neo_agent.cli``."""

    parser = argparse.ArgumentParser(description="Run a Project NEO agent")
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to an agent configuration JSON file",
    )

    arguments = parser.parse_args(argv)

    configuration = load_configuration(arguments.config)
    runtime = AgentRuntime(configuration)
    runtime.initialize()

    runtime.dispatch({"input": "Hello from the CLI"})

    return 0


if __name__ == "__main__":  # pragma: no cover - manual invocation helper
    raise SystemExit(main())
