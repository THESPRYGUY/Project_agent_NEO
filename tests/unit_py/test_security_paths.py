import os
from pathlib import Path
import sys
import pytest


def _ensure_import_path():
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    srcp = root / "src"
    if str(srcp) not in sys.path:
        sys.path.insert(0, str(srcp))


def test_is_safe_subpath_blocks_symlink_escape(tmp_path: Path):
    _ensure_import_path()
    from neo_agent.intake_app import IntakeApplication

    root = tmp_path / "root"
    root.mkdir(parents=True, exist_ok=True)

    # Control cases
    assert IntakeApplication._is_safe_subpath(root, root) is True
    safe_child = root / "child"
    safe_child.mkdir()
    assert IntakeApplication._is_safe_subpath(root, safe_child) is True

    # Symlink escape: create a link inside root pointing to parent of root
    target = root.parent
    link = root / "escape"
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
    except (
        OSError,
        NotImplementedError,
    ):  # pragma: no cover - platforms without symlink perms
        pytest.skip("symlink not supported on this platform")

    # Candidate resolves outside root, should be rejected
    assert IntakeApplication._is_safe_subpath(root, link) is False
