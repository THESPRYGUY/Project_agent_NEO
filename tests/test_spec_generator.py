"""Tests for the agent spec generator and LinkedIn scraping helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from neo_agent.linkedin import scrape_linkedin_profile
from neo_agent.spec_generator import build_agent_configuration, generate_agent_specs


def test_generate_agent_specs(tmp_path: Path) -> None:
    profile = {
        "agent": {
            "name": "Atlas Analyst",
            "version": "1.0.0",
            "persona": "Adaptive analyst",
            "domain": "Finance",
            "role": "Enterprise Analyst",
        },
        "toolsets": {
            "selected": ["Data Analysis", "Reporting"],
            "custom": ["Risk Modeling"],
        },
        "attributes": {
            "selected": ["Detail Oriented"],
            "custom": ["Resilient"],
        },
        "preferences": {
            "sliders": {"autonomy": 80, "confidence": 70, "collaboration": 65},
            "communication_style": "Concise",
            "collaboration_mode": "Cross-Functional",
        },
        "notes": "Focus on quarterly variance analysis",
        "linkedin": {"roles": ["analyst"]},
    }

    output = generate_agent_specs(profile, tmp_path)

    config_path = output["agent_config"]
    with config_path.open("r", encoding="utf-8") as handle:
        config_data = json.load(handle)

    assert config_data["name"] == "Atlas Analyst"
    assert config_data["metadata"]["domain"] == "Finance"
    assert len(config_data["skills"]) >= 2

    manifest_path = output["agent_manifest"]
    assert manifest_path.exists()

    preferences_path = output["agent_preferences"]
    with preferences_path.open("r", encoding="utf-8") as handle:
        preferences = json.load(handle)
    assert preferences["sliders"]["autonomy"] == 80


def test_build_agent_configuration_fallback_skill() -> None:
    profile = {"agent": {"name": "Minimal", "version": "0.1"}}
    configuration = build_agent_configuration(profile)
    assert configuration.skill_map()["echo"].entrypoint == "neo_agent.skills:echo"


def test_scrape_linkedin_profile_handles_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from urllib import error, request

    def _raise(*_args, **_kwargs):
        raise error.URLError("failure")

    monkeypatch.setattr(request, "urlopen", _raise)

    result = scrape_linkedin_profile("https://example.com")
    assert "error" in result


def test_scrape_linkedin_profile_extracts_keywords(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def read(self) -> bytes:
            return self.text.encode("utf-8")

        def __enter__(self):  # pragma: no cover - context helper
            return self

        def __exit__(self, exc_type, exc, tb):  # pragma: no cover - context helper
            return False

    html = """
    <html>
      <head>
        <title>Senior Data Scientist</title>
        <meta name="description" content="AI leader in finance and marketing">
      </head>
      <body>
        Experienced data scientist with expertise in python, sql, and cloud automation.
        Certified Analytics Professional.
      </body>
    </html>
    """

    from urllib import request

    monkeypatch.setattr(request, "urlopen", lambda *args, **kwargs: DummyResponse(html))

    result = scrape_linkedin_profile("https://example.com/profile")
    assert "finance" in [item.lower() for item in result.get("domain_expertise", [])]
    assert "python" in [item.lower() for item in result.get("skills", [])]
    assert result.get("headline") == "Senior Data Scientist"

