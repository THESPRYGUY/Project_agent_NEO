from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest


# Ensure src/ is importable for all tests (CI and local)
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (ROOT, SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Stable, non-synced outdir in CI/local
_default_root = Path(os.getenv("RUNNER_TEMP", Path.cwd() / "_generated_ci"))
DEFAULT_OUTDIR = _default_root / "_generated"

os.environ.setdefault("NEO_REPO_OUTDIR", str(DEFAULT_OUTDIR))
os.environ.setdefault("NEO_COPY_TO_ONEDRIVE", "false")
os.environ.setdefault("FAIL_ON_PARITY", "false")
os.environ.setdefault("NEO_APPLY_OVERLAYS", "false")

DEFAULT_OUTDIR.mkdir(parents=True, exist_ok=True)


def pytest_collection_modifyitems(config, items):
    """Default all tests to 'unit' unless explicitly marked otherwise.

    - If a test has @pytest.mark.integ or @pytest.mark.smoke, leave it.
    - If it already has @pytest.mark.unit, leave it.
    - Else, add @pytest.mark.unit to make unit the default selection.
    """
    for item in items:
        marks = {m.name for m in item.iter_markers()}
        if not ("integ" in marks or "smoke" in marks or "unit" in marks):
            item.add_marker(pytest.mark.unit)
