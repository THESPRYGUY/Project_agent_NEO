from __future__ import annotations

import re
from typing import Dict, Iterable


_PAT = re.compile(r"\s*(PRI|HAL|AUD)\s*([<>]=?)\s*([0-9]*\.?[0-9]+)\s*")


def parse_activation_strings(items: Iterable[str] | None) -> Dict[str, float]:
    """
    Parse gate activation strings to a normalized dict.

    items: list[str] like ["PRI>=0.95","HAL<=0.02","AUD>=0.9"]
    returns: {"PRI_min": 0.95, "HAL_max": 0.02, "AUD_min": 0.9}
    """
    out: Dict[str, float] = {}
    if not items:
        return out
    for s in items:
        try:
            m = _PAT.match(str(s))
            if not m:
                continue
            key, op, val = m.group(1), m.group(2), float(m.group(3))
            if key == "PRI":
                out["PRI_min"] = val
            elif key == "HAL":
                out["HAL_max"] = val
            elif key == "AUD":
                out["AUD_min"] = val
        except Exception:
            # Skip malformed; caller uses defaults when missing
            continue
    return out

