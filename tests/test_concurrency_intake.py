from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from neo_agent.intake_app import create_app
from neo_agent import telemetry

# Simple concurrency stress test to ensure no cross-request leakage or crashes.
# We don't assert extremely tight timing, just structural integrity and isolation.


def _payload(i: int) -> dict[str, list[str]]:
    base = {
        "agent_name": [f"Agent {i}"],
        "agent_version": ["1.0.0"],
        "agent_persona": ["ENTJ"],
        "domain": ["Finance"],
        "role": ["Enterprise Analyst"],
        "toolsets": ["Data Analysis"],
        "attributes": ["Strategic"],
        "autonomy": ["55"],
        "confidence": ["50"],
        "collaboration": ["40"],
        "communication_style": ["Formal"],
        "collaboration_mode": ["Solo"],
        "notes": ["Concurrency run"],
    }
    selector = {
        "topLevel": "Strategic Functions",
        "subdomain": "Workflow Orchestration",
        "tags": [f"tag{i}", "Shared", str(i % 3)],
    }
    base["domain_selector"] = [json.dumps(selector)]
    return base


def test_concurrent_profile_builds_isolation(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)
    telemetry.clear_buffer()

    results: list[dict[str, Any]] = []
    errors: list[str] = []
    lock = threading.Lock()

    def worker(idx: int) -> None:
        try:
            payload = _payload(idx)
            profile = app._build_profile(payload, {})
            with lock:
                results.append(profile)
        except Exception as exc:  # pragma: no cover - failure path
            with lock:
                errors.append(str(exc))

    # Run 100 concurrent builds (size tradeoff for CI speed vs coverage)
    with ThreadPoolExecutor(max_workers=20) as ex:
        for i in range(100):
            ex.submit(worker, i)

    assert not errors, f"Encountered errors: {errors}"  # no exceptions
    assert len(results) == 100

    # Ensure each profile has its own tag set normalized and no global bleed (e.g., growing list)
    lengths = {len(p["agent"].get("domain_selector", {}).get("tags", [])) for p in results}
    assert len(lengths) == 1  # all same length
    # Telemetry events should be at least equal to number of profiles (changed + validated + persona)
    events = telemetry.get_buffered_events()
    assert len(events) >= 100

    # Ensure no tag from one is unexpectedly mutated into another (check prefix uniqueness by included tagX)
    observed_tagx = set()
    for p in results:
        ds = p["agent"].get("domain_selector")
        assert ds is not None
        tags = ds.get("tags", [])
        # Expect a tag with pattern tagN present
        matching = [t for t in tags if t.startswith("tag")]  # slugging preserves
        assert matching, f"Missing tag* in {tags}"
        observed_tagx.update(matching)

    # We should see many distinct tagN values ( > 80 )
    assert len(observed_tagx) > 80
