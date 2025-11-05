"""Writer utilities for normalising sensitive payload fields."""

from __future__ import annotations

from typing import Iterable, List

_PII_MAP = {
    "hash": "hash",
    "hashed": "hash",
    "hash_only": "hash",
    "hashing": "hash",
    "mask": "mask",
    "masked": "mask",
    "mask_only": "mask",
    "masking": "mask",
    "none": "none",
    "no": "none",
    "unset": "none",
    "n/a": "none",
}
_VALID_PII = {"hash", "mask", "none"}


def normalise_pii_flags(flags: Iterable[str | None]) -> List[str]:
    """Normalise PII flags to canonical ``hash``/``mask``/``none`` values.

    Unknown or custom values are coerced to ``mask`` to ensure safest handling.
    Duplicate flags preserve first-seen order, and ``none`` is dropped when other
    flags are present.
    """

    seen: set[str] = set()
    result: List[str] = []

    for flag in flags or []:
        token = str(flag or "").strip().lower()
        if not token:
            continue
        token = _PII_MAP.get(token, token)
        if token not in _VALID_PII:
            token = "mask"
        if token == "none" and seen:
            continue
        if token != "none" and "none" in seen:
            seen.remove("none")
            result = [item for item in result if item != "none"]
        if token not in seen:
            seen.add(token)
            result.append(token)

    if not result:
        result = ["none"]
    return result


__all__ = ["normalise_pii_flags"]
