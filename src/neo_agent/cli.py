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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Project NEO agent")
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to an agent configuration JSON file",
    )

    subparsers = parser.add_subparsers(dest="command")
    parser.set_defaults(handler=_run_agent_command)

    serve_parser = subparsers.add_parser(
        "serve", help="Run the Project NEO intake form HTTP server"
    )
    serve_parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host interface to bind (default: $env:HOST or 127.0.0.1)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind (default: $env:PORT or 5000)",
    )
    serve_parser.set_defaults(handler=_serve_command)

    naics_reload = subparsers.add_parser(
        "naics-reload", help="Reload NAICS reference data (warms prefix index)"
    )
    naics_reload.add_argument(
        "--base-dir", type=Path, default=None, help="Base directory for intake app (tests/run)"
    )
    naics_reload.set_defaults(handler=_naics_reload_command)

    return parser


def _run_agent_command(arguments: argparse.Namespace) -> int:
    configuration = load_configuration(arguments.config)
    runtime = AgentRuntime(configuration)
    runtime.initialize()
    runtime.dispatch({"input": "Hello from the CLI"})
    return 0


def _serve_command(arguments: argparse.Namespace) -> int:
    from .intake_app import create_app

    app = create_app()
    app.serve(host=arguments.host, port=arguments.port)
    return 0


def _naics_reload_command(arguments: argparse.Namespace) -> int:
    """Reload NAICS reference by instantiating an IntakeApplication and clearing its cache.

    This is a lightweight helper primarily for operational workflows; it validates that the
    reference file can be parsed and the prefix index built. Success prints stats to stdout.
    """
    from .intake_app import create_app
    app = create_app(base_dir=arguments.base_dir)
    # Ensure initial load (optional) to show delta
    initial = app._load_naics_reference()
    before = len(initial)
    count = app.reload_naics()
    after_cache = app._load_naics_reference()
    prefix_index = getattr(app, "_naics_prefix_index", {})
    prefix_keys = len(prefix_index) if isinstance(prefix_index, dict) else 0
    if count == 0:
        print("NAICS reload failed; cache unchanged (entries=%d)" % before)
        return 1
    print(
        "NAICS reload successful: entries=%d (was %d) prefix_keys=%d" % (
            len(after_cache), before, prefix_keys
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point used by ``python -m neo_agent.cli``."""

    parser = _build_parser()
    arguments = parser.parse_args(argv)
    handler = getattr(arguments, "handler", None)
    if handler is None:
        parser.error("No command handler configured")
    return handler(arguments)


if __name__ == "__main__":  # pragma: no cover - manual invocation helper
    raise SystemExit(main())
