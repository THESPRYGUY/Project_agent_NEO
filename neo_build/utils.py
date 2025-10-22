"""Utility helpers for deterministic JSON writing and slugging."""

from __future__ import annotations

import errno
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


_SLUG_SAFE = re.compile(r"[^a-z0-9\-]+")


def slugify(text: str) -> str:
    """Return a filesystem-safe slug for ``text``.

    Lowercases, replaces whitespace with dashes, and strips unsafe chars.
    """

    value = (text or "").strip().lower()
    value = value.replace("_", "-")
    value = re.sub(r"\s+", "-", value)
    value = _SLUG_SAFE.sub("-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def deep_sorted(value: Any) -> Any:
    """Deep-sort lists and dict keys for deterministic JSON output."""

    if isinstance(value, dict):
        return {k: deep_sorted(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        # Sort simple scalars; otherwise sort by JSON string
        try:
            return [deep_sorted(v) for v in sorted(value, key=_sort_key)]
        except Exception:
            return [deep_sorted(v) for v in value]
    return value


def _sort_key(item: Any) -> Any:
    if isinstance(item, (str, int, float)):
        return item
    try:
        return json.dumps(item, sort_keys=True, ensure_ascii=False)
    except Exception:
        return str(item)


def json_write(path: Path, payload: Mapping[str, Any] | Any) -> None:
    """Write ``payload`` to ``path`` in canonical UTF-8 with sorted keys."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(deep_sorted(payload), handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


class FileLock:
    """A lightweight process lock using exclusive file creation.

    Not robust across NFS but sufficient for local builds. Creates ``.lock``.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def acquire(self) -> None:
        try:
            # Use os.O_EXCL to fail if exists
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except OSError as exc:  # pragma: no cover - platform variance
            if exc.errno == errno.EEXIST:
                raise RuntimeError(f"Build already locked by {self.path}") from exc
            raise

    def release(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except Exception:
            # Non-fatal
            pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False

