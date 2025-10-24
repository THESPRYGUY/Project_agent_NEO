from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neo_build.gates import parse_activation_strings


def test_parse_activation_strings_basic():
    items = ["PRI>=0.95", "HAL<=0.02", "AUD>=0.9"]
    out = parse_activation_strings(items)
    assert out == {"PRI_min": 0.95, "HAL_max": 0.02, "AUD_min": 0.9}


def test_parse_activation_strings_spaces_and_order():
    items = ["  HAL <= 0.020 ", "AUD >=0.90", "PRI  >=  0.950"]
    out = parse_activation_strings(items)
    assert out["PRI_min"] == 0.95
    assert out["HAL_max"] == 0.02
    assert out["AUD_min"] == 0.9


def test_parse_activation_strings_ignores_malformed():
    items = ["X>=0.5", "PRI>>0.9", "AUD", "HAL <= 0.02"]
    out = parse_activation_strings(items)
    assert out == {"HAL_max": 0.02}
