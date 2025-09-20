"""Utilities for loading and inspecting NEO agent pack specifications.

This module provides a CLI oriented helper that discovers JSON pack
definitions in the repository, validates their core structure, and prints a
human friendly summary of their workflow contents.  It is intentionally light
weight so it can be used during development or in CI pipelines to ensure the
configuration library stays well-formed.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


JsonDict = Dict[str, Any]


@dataclass
class ValidationResult:
    """Container describing a loaded pack and any validation issues."""

    path: Path
    payload: JsonDict
    missing_keys: Sequence[str]

    @property
    def name(self) -> str:
        return self.payload.get("id") or self.payload.get("pack") or self.path.name


def discover_pack_files(root: Path) -> List[Path]:
    """Return all JSON files in ``root`` (non-recursive) sorted by name."""

    return sorted(p for p in root.glob("*.json") if p.is_file())


def load_json(path: Path) -> JsonDict:
    """Load a JSON document from disk."""

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def required_top_level_keys(path: Path) -> Iterable[str]:
    """Infer the required top-level keys for a pack based on its filename."""

    name = path.stem
    if "Workflow-Pack" in name:
        return ["pack", "version", "graphs"]
    if "Memory-Schema" in name:
        return ["id", "version", "principles", "retention"]
    if "Reporting-Pack" in name:
        return ["id", "version", "exec_brief"]
    # Fallback to minimal expectations for unknown packs.
    return ["version"]


def validate_pack(path: Path) -> ValidationResult:
    """Load and validate a pack returning the validation outcome."""

    try:
        payload = load_json(path)
    except FileNotFoundError as exc:  # pragma: no cover - defensive guard
        raise FileNotFoundError(f"Pack file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    required = set(required_top_level_keys(path))
    missing = sorted(key for key in required if key not in payload)
    return ValidationResult(path=path, payload=payload, missing_keys=missing)


def graph_node_id(node: Any) -> str:
    """Return the canonical node identifier from a node entry."""

    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        for key in ("id", "name", "node", "label"):
            value = node.get(key)
            if isinstance(value, str) and value:
                return value
    raise ValueError(f"Unable to determine node identifier from: {node!r}")


def graph_node_type(node: Any) -> str:
    if isinstance(node, dict):
        return str(node.get("type", "unspecified"))
    return "unspecified"


def graph_node_params(node: Any) -> JsonDict:
    if isinstance(node, dict):
        return {
            key: value
            for key, value in node.items()
            if key not in {"id", "name", "label", "node", "type"}
        }
    return {}


def build_adjacency(edges: Sequence[Sequence[str]]) -> Tuple[Dict[str, List[str]], Dict[str, int]]:
    adjacency: Dict[str, List[str]] = defaultdict(list)
    indegree: Dict[str, int] = defaultdict(int)
    for edge in edges:
        if len(edge) != 2:
            raise ValueError(f"Edge definition must contain exactly two entries: {edge!r}")
        src, dst = edge
        adjacency[src].append(dst)
        indegree.setdefault(src, indegree.get(src, 0))
        indegree[dst] += 1
    return adjacency, indegree


def topological_order(nodes: Sequence[str], edges: Sequence[Sequence[str]]) -> List[str]:
    """Compute a simple topological ordering for a workflow graph."""

    adjacency, indegree = build_adjacency(edges)
    indegree = {node: indegree.get(node, 0) for node in nodes}
    queue: deque[str] = deque(sorted(node for node, degree in indegree.items() if degree == 0))
    order: List[str] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbour in adjacency.get(node, []):
            indegree[neighbour] -= 1
            if indegree[neighbour] == 0:
                queue.append(neighbour)

    if len(order) != len(nodes):
        raise ValueError("Workflow graph contains cycles or disconnected nodes")
    return order


def summarize_workflow_graph(graph: JsonDict) -> None:
    graph_id = graph.get("id", "<unknown>")
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    node_ids = [graph_node_id(node) for node in nodes]
    execution_order = topological_order(node_ids, edges)

    print(f"  Graph: {graph_id}")
    print(f"    Nodes ({len(nodes)}): {', '.join(node_ids)}")
    print(f"    Edges ({len(edges)}): {', '.join(f'{src}->{dst}' for src, dst in edges)}")
    print(f"    Execution order: {', '.join(execution_order)}")

    for raw_node in nodes:
        node_id = graph_node_id(raw_node)
        node_type = graph_node_type(raw_node)
        params = graph_node_params(raw_node)
        print(f"      Node {node_id} | type={node_type} | params={params if params else '{}'}")


def summarize_pack(result: ValidationResult) -> None:
    print(f"Pack: {result.name} ({result.path.name})")
    if result.missing_keys:
        print(f"  Missing required keys: {', '.join(result.missing_keys)}")

    payload = result.payload
    if "graphs" in payload and isinstance(payload["graphs"], list):
        print("  Workflow graphs:")
        for graph in payload["graphs"]:
            summarize_workflow_graph(graph)
    else:
        print(f"  Top-level keys: {', '.join(sorted(payload.keys()))}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and summarise NEO agent packs")
    parser.add_argument(
        "root",
        nargs="?",
        default=Path.cwd(),
        type=Path,
        help="Directory to scan for pack JSON files (defaults to current working directory).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    root: Path = args.root
    files = discover_pack_files(root)
    if not files:
        print(f"No JSON pack files found in {root}")
        return 0

    exit_code = 0
    for file_path in files:
        try:
            result = validate_pack(file_path)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Error processing {file_path}: {exc}")
            exit_code = 1
            continue

        summarize_pack(result)
        if result.missing_keys:
            exit_code = 1

    return exit_code


if __name__ == "__main__":  # pragma: no cover - exercised via CLI
    raise SystemExit(main())

