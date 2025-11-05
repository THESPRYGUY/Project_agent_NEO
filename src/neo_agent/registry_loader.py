"""Utility helpers for loading the tool & data registry (pack 12).

The loader ensures that interactive UI components and contract samples
stay aligned with the canonical `12_Tool+Data-Registry_v2.json` pack.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_PACK_FILENAME = "12_Tool+Data-Registry_v2.json"
_DEFAULT_BUILD_ROOT = (
    Path(__file__).resolve().parents[2] / "generated_repos" / "agent-build-007-2-1-1"
)
_REGISTRY_CACHE: Dict[Path, "RegistrySnapshot"] = {}


@dataclass(frozen=True)
class RegistryConnector:
    """Normalized connector entry sourced from the registry pack."""

    id: str
    name: str
    scopes: List[str]
    secret_ref: str
    enabled: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "scopes": list(self.scopes),
            "secret_ref": self.secret_ref,
            "enabled": self.enabled,
        }


@dataclass(frozen=True)
class RegistryDataset:
    """Normalized dataset entry sourced from the registry pack."""

    id: str
    name: str
    description: str
    classification: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "classification": self.classification,
        }


@dataclass(frozen=True)
class RegistrySnapshot:
    """Structured view of pack-12 registry content."""

    connectors: List[RegistryConnector]
    data_sources: List[str]
    datasets: List[RegistryDataset]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connectors": [conn.to_dict() for conn in self.connectors],
            "data_sources": list(self.data_sources),
            "datasets": [dataset.to_dict() for dataset in self.datasets],
        }


def _candidate_roots(explicit: Optional[Path]) -> Iterable[Path]:
    """Yield candidate directories that may contain the registry pack."""

    if explicit:
        yield explicit

    env_root = os.getenv("NEO_REGISTRY_ROOT")
    if env_root:
        yield Path(env_root)

    repo_outdir = os.getenv("NEO_REPO_OUTDIR")
    if repo_outdir:
        root = Path(repo_outdir)
        last_path = root / "_last_build.json"
        if last_path.exists():
            try:
                data = json.loads(last_path.read_text(encoding="utf-8"))
                outdir = data.get("outdir")
                if outdir:
                    yield Path(str(outdir))
            except Exception:
                # Ignore malformed last-build pointers; fall back to defaults.
                pass
        yield root

    yield _DEFAULT_BUILD_ROOT


def _resolve_pack_path(root: Optional[Path]) -> Path:
    """Resolve the file path for `12_Tool+Data-Registry_v2.json`."""

    for candidate_root in _candidate_roots(root):
        candidate = candidate_root
        if candidate.name == _PACK_FILENAME and candidate.is_file():
            return candidate
        if candidate.is_dir():
            pack_path = candidate / _PACK_FILENAME
            if pack_path.exists():
                return pack_path
    raise FileNotFoundError(f"Unable to locate {_PACK_FILENAME}")


def _normalise_id(value: Any) -> str:
    text = str(value or "").strip()
    return text


def _load_json(path: Path) -> Dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"Registry pack must be an object: {path}")
    return data


def _empty_snapshot() -> RegistrySnapshot:
    return RegistrySnapshot(connectors=[], data_sources=[], datasets=[])


def _snapshot_from_payload(payload: Dict[str, Any]) -> RegistrySnapshot:
    connectors: List[RegistryConnector] = []
    for item in payload.get("connectors") or []:
        if not isinstance(item, dict):
            continue
        ident = _normalise_id(item.get("id") or item.get("name"))
        if not ident:
            continue
        connectors.append(
            RegistryConnector(
                id=ident,
                name=_normalise_id(item.get("name") or ident),
                scopes=[
                    _normalise_id(scope)
                    for scope in item.get("scopes") or []
                    if _normalise_id(scope)
                ],
                secret_ref=_normalise_id(item.get("secret_ref")),
                enabled=bool(item.get("enabled", True)),
            )
        )
    connectors.sort(key=lambda conn: conn.name.casefold())

    data_sources = sorted(
        {
            _normalise_id(src)
            for src in payload.get("data_sources") or []
            if _normalise_id(src)
        },
        key=str.casefold,
    )

    datasets: List[RegistryDataset] = []
    for item in payload.get("datasets") or []:
        if not isinstance(item, dict):
            continue
        ident = _normalise_id(item.get("id") or item.get("name"))
        if not ident:
            continue
        datasets.append(
            RegistryDataset(
                id=ident,
                name=_normalise_id(item.get("name") or ident),
                description=_normalise_id(item.get("description")),
                classification=_normalise_id(item.get("classification")),
            )
        )
    datasets.sort(key=lambda dataset: dataset.name.casefold())

    return RegistrySnapshot(
        connectors=connectors, data_sources=data_sources, datasets=datasets
    )


def clear_registry_cache() -> None:
    """Reset the in-memory registry cache (primarily for tests)."""

    _REGISTRY_CACHE.clear()


def load_tool_registry(root: Optional[Path | str] = None) -> RegistrySnapshot:
    """Load and normalise tool/data registry content.

    Parameters
    ----------
    root:
        Optional base directory (or direct pack path) to resolve the pack file.
        When omitted, the loader honours `NEO_REGISTRY_ROOT`, then
        `NEO_REPO_OUTDIR` (and its `_last_build.json` pointer), finally falling
        back to the checked-in baseline under
        `generated_repos/agent-build-007-2-1-1`.

    Returns
    -------
    RegistrySnapshot
        Connectors, data sources, and datasets ready for UI bindings.
    """
    explicit = Path(root) if root is not None else None
    if explicit is not None and explicit.name == _PACK_FILENAME:
        if explicit.exists():
            pack_path = explicit
        else:
            return _empty_snapshot()
    else:
        try:
            pack_path = _resolve_pack_path(explicit)
        except FileNotFoundError:
            return _empty_snapshot()

    cache_key = pack_path.resolve()
    if cache_key in _REGISTRY_CACHE:
        return _REGISTRY_CACHE[cache_key]

    try:
        payload = _load_json(pack_path)
    except (ValueError, json.JSONDecodeError, OSError):
        snapshot = _empty_snapshot()
    else:
        snapshot = _snapshot_from_payload(payload)

    _REGISTRY_CACHE[cache_key] = snapshot
    return snapshot


__all__ = [
    "RegistryConnector",
    "RegistryDataset",
    "RegistrySnapshot",
    "load_tool_registry",
    "clear_registry_cache",
]
