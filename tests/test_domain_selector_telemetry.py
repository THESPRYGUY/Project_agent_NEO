"""Tests telemetry events for domain selector (Step 4)."""
from __future__ import annotations

import json
from pathlib import Path

from neo_agent.intake_app import create_app
from neo_agent.telemetry import get_buffered_events, clear_buffer


def test_domain_selector_telemetry_success(tmp_path: Path) -> None:
    clear_buffer()
    app = create_app(base_dir=tmp_path)
    payload = {
        "agent_name": ["Telemetry Agent"],
        "agent_version": ["1.0.0"],
        "agent_persona": ["ENTJ"],
        "domain": ["Finance"],
        "role": ["Enterprise Analyst"],
        "domain_selector": [json.dumps({
            "topLevel": "Strategic Functions",
            "subdomain": "Workflow Orchestration",
            "tags": ["ops"],
        })]
    }
    app._build_profile(payload, {})
    events = get_buffered_events()
    names = [e['name'] for e in events]
    assert 'domain_selector:changed' in names
    assert 'domain_selector:validated' in names
    assert 'domain_selector:error' not in names


def test_domain_selector_telemetry_error_missing_naics(tmp_path: Path) -> None:
    clear_buffer()
    app = create_app(base_dir=tmp_path)
    payload = {
        "agent_name": ["Telemetry Agent"],
        "agent_version": ["1.0.0"],
        "agent_persona": ["ENTJ"],
        "domain": ["Finance"],
        "role": ["Enterprise Analyst"],
        "domain_selector": [json.dumps({
            "topLevel": "Sector Domains",
            "subdomain": "Energy & Infrastructure",
            "tags": []
        })]
    }
    app._build_profile(payload, {})
    events = get_buffered_events()
    names = [e['name'] for e in events]
    assert 'domain_selector:changed' in names
    assert 'domain_selector:validated' not in names
    assert 'domain_selector:error' in names


def test_domain_selector_telemetry_error_invalid_code(tmp_path: Path) -> None:
    clear_buffer()
    app = create_app(base_dir=tmp_path)
    payload = {
        "agent_name": ["Telemetry Agent"],
        "agent_version": ["1.0.0"],
        "agent_persona": ["ENTJ"],
        "domain": ["Finance"],
        "role": ["Enterprise Analyst"],
        "domain_selector": [json.dumps({
            "topLevel": "Sector Domains",
            "subdomain": "Energy & Infrastructure",
            "tags": [],
            "naics": {"code": "999999"}
        })]
    }
    app._build_profile(payload, {})
    events = get_buffered_events()
    assert any(e['name'] == 'domain_selector:error' and '999999' in e['payload'].get('message','') for e in events)
