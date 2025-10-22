"""NEO build system: contracts, validators, writers, and utilities.

Pure-stdlib helpers for generating deterministic 20-pack agent repos.
"""

from .contracts import (
    CANONICAL_PACK_FILENAMES,
    KPI_TARGETS,
    REQUIRED_EVENTS,
    REQUIRED_ALERTS,
    REQUIRED_HUMAN_GATE_ACTIONS,
)

__all__ = [
    "CANONICAL_PACK_FILENAMES",
    "KPI_TARGETS",
    "REQUIRED_EVENTS",
    "REQUIRED_ALERTS",
    "REQUIRED_HUMAN_GATE_ACTIONS",
]

