"""Test intake flow repo generation and state persistence."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest

from neo_agent.intake_app import IntakeApplication


@pytest.fixture
def temp_base_dir(tmp_path: Path) -> Path:
    """Create a temporary base directory with required data structure."""
    base = tmp_path / "test_workspace"
    base.mkdir(parents=True, exist_ok=True)

    # Copy essential data files from the actual project
    project_root = Path(__file__).resolve().parents[1]
    data_src = project_root / "data"
    data_dst = base / "data"

    if data_src.exists():
        import shutil

        shutil.copytree(data_src, data_dst, dirs_exist_ok=True)

    return base


@pytest.fixture
def app(temp_base_dir: Path) -> IntakeApplication:
    """Create an IntakeApplication instance for testing."""
    return IntakeApplication(base_dir=temp_base_dir)


def test_post_generates_full_repo(app: IntakeApplication, temp_base_dir: Path):
    """Test that POST "/" generates a complete repo with all 20+ files."""
    form_data = {
        "agent_name": "Test Legal Agent",
        "agent_version": "1.0.0",
        "naics_code": "541110",
        "naics_title": "Offices of Lawyers",
        "naics_level": "6",
        "naics_lineage_json": json.dumps(
            [
                {"code": "54", "title": "Professional Services", "level": 2},
                {"code": "5411", "title": "Legal Services", "level": 4},
                {"code": "541110", "title": "Offices of Lawyers", "level": 6},
            ]
        ),
        "business_function": "Legal & Compliance",
        "role_code": "AIA-P",
        "role_title": "Legal & Compliance Lead",
        "role_seniority": "Principal",
        "identity.agent_id": "test-agent-id-123",
        "identity.display_name": "Test Legal Agent",
        "identity.owners": "CAIO,CPA",
        "identity.no_impersonation": "true",
    }

    # Simulate POST request
    body = urlencode(form_data, doseq=True).encode("utf-8")
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": type("FakeInput", (), {"read": lambda self, n: body})(),
    }

    responses = []

    def start_response(status: str, headers: list):
        responses.append((status, headers))

    result = list(app.wsgi_app(environ, start_response))

    # Check that response is successful
    assert len(responses) == 1
    assert responses[0][0] == "200 OK"

    # Check that SoT repo was created under _generated via last-build pointer
    last_path = temp_base_dir / "_generated" / "_last_build.json"
    assert last_path.exists(), "_last_build.json should exist after save"
    last = json.loads(last_path.read_text(encoding="utf-8"))
    repo_dir = Path(last["outdir"])  # authoritative pack path

    # Check for essential files
    readme_file = repo_dir / "01_README+Directory-Map_v2.json"
    integrity_file = repo_dir / "INTEGRITY_REPORT.json"

    assert (
        readme_file.exists()
    ), f"01_README+Directory-Map_v2.json should exist in {repo_dir}"
    assert integrity_file.exists(), f"INTEGRITY_REPORT.json should exist in {repo_dir}"

    # Count files in repo (should be 20+ files)
    json_files = list(repo_dir.glob("*.json"))
    assert (
        len(json_files) >= 10
    ), f"Should have at least 10 JSON files, found {len(json_files)}"


def test_api_agent_generate_endpoint(app: IntakeApplication, temp_base_dir: Path):
    """Test that /api/agent/generate endpoint creates a repo."""
    profile = {
        "agent": {
            "name": "API Test Agent",
            "version": "1.0.0",
        },
        "identity": {
            "agent_id": "api-test-123",
            "display_name": "API Test Agent",
        },
        "business_function": "Finance & Accounting",
        "role": {
            "code": "AIA-M",
            "title": "Financial Controller",
            "seniority": "Manager",
        },
        "classification": {
            "naics": {
                "code": "541211",
                "title": "Offices of Certified Public Accountants",
                "level": 6,
            }
        },
        "context": {"region": ["US"]},
    }

    body = json.dumps({"profile": profile}).encode("utf-8")
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/api/agent/generate",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": type("FakeInput", (), {"read": lambda self, n: body})(),
    }

    responses = []

    def start_response(status: str, headers: list):
        responses.append((status, headers))

    result = list(app.wsgi_app(environ, start_response))

    # Check response
    assert len(responses) == 1
    assert responses[0][0] == "200 OK"

    # Parse response JSON
    response_data = json.loads(b"".join(result).decode("utf-8"))
    assert response_data.get("status") == "ok"
    assert "out_dir" in response_data
    assert "checks" in response_data

    # Verify repo was created in generated_repos for API endpoint
    repos_dir = temp_base_dir / "generated_repos"
    assert repos_dir.exists()


def test_agent_id_persists_across_rerender(app: IntakeApplication, temp_base_dir: Path):
    """Test that agent_id persists in the form after submission."""
    test_agent_id = "persistent-agent-123"

    form_data = {
        "agent_name": "Persistent Agent",
        "agent_version": "1.0.0",
        "naics_code": "541110",
        "naics_title": "Offices of Lawyers",
        "naics_level": "6",
        "naics_lineage_json": "[]",
        "business_function": "Legal & Compliance",
        "role_code": "AIA-P",
        "role_title": "Legal Lead",
        "identity.agent_id": test_agent_id,
        "identity.display_name": "Persistent Agent",
    }

    body = urlencode(form_data, doseq=True).encode("utf-8")
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": type("FakeInput", (), {"read": lambda self, n: body})(),
    }

    responses = []

    def start_response(status: str, headers: list):
        responses.append((status, headers))

    result = list(app.wsgi_app(environ, start_response))
    html_response = b"".join(result).decode("utf-8")

    # Check that agent_id is in the re-rendered form
    assert (
        test_agent_id in html_response
    ), "Agent ID should be preserved in the re-rendered form"
    assert (
        f'value="{test_agent_id}"' in html_response
        or f"value=&quot;{test_agent_id}&quot;" in html_response
    )


def test_function_role_state_persists(app: IntakeApplication, temp_base_dir: Path):
    """Test that business function and role selections persist via FUNCTION_ROLE_STATE."""
    form_data = {
        "agent_name": "State Test Agent",
        "agent_version": "1.0.0",
        "naics_code": "541110",
        "naics_title": "Offices of Lawyers",
        "naics_level": "6",
        "naics_lineage_json": "[]",
        "business_function": "Legal & Compliance",
        "role_code": "AIA-P",
        "role_title": "Legal Lead",
        "role_seniority": "Principal",
        "identity.agent_id": "state-test-123",
        "identity.display_name": "State Test Agent",
    }

    body = urlencode(form_data, doseq=True).encode("utf-8")
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": type("FakeInput", (), {"read": lambda self, n: body})(),
    }

    responses = []

    def start_response(status: str, headers: list):
        responses.append((status, headers))

    result = list(app.wsgi_app(environ, start_response))
    html_response = b"".join(result).decode("utf-8")

    # Check that FUNCTION_ROLE_STATE is set in the JavaScript
    assert "window.__FUNCTION_ROLE_STATE__" in html_response

    # Extract and verify the state
    import re

    state_match = re.search(
        r"window\.__FUNCTION_ROLE_STATE__\s*=\s*(\{[^;]+\});", html_response
    )
    assert state_match, "FUNCTION_ROLE_STATE should be present in the page"

    state_json = state_match.group(1)
    state = json.loads(state_json)

    assert state.get("business_function") == "Legal & Compliance"
    assert state.get("role_code") == "AIA-P"
    assert state.get("role_title") == "Legal Lead"
    assert state.get("role_seniority") == "Principal"


def test_normalization_with_empty_region(app: IntakeApplication):
    """Test that normalization handles empty region gracefully."""
    from neo_agent.adapters.normalize_v3 import normalize_context_role

    v3_payload = {
        "context": {
            "naics": {
                "code": "541110",
                "title": "Offices of Lawyers",
                "level": 6,
            },
            "region": [],  # Empty region
        },
        "role": {
            "function_code": "Legal & Compliance",
            "role_code": "AIA-P",
            "role_title": "Legal Lead",
            "objectives": ["Ensure compliance"],
        },
    }

    result = normalize_context_role(v3_payload)

    # Should default to CA when region is empty
    assert result["sector_profile"]["region"] == ["CA"]
    assert "NIST_AI_RMF" in result["sector_profile"]["regulatory"]
    assert "PIPEDA" in result["sector_profile"]["regulatory"]

    # Role profile should be set correctly
    assert result["role_profile"]["archetype"] == "AIA-P"
    assert result["role_profile"]["role_title"] == "Legal Lead"
    assert result["role_profile"]["objectives"] == ["Ensure compliance"]


def test_normalization_with_region(app: IntakeApplication):
    """Test that normalization uses provided region."""
    from neo_agent.adapters.normalize_v3 import normalize_context_role

    v3_payload = {
        "context": {
            "naics": {
                "code": "541110",
                "title": "Offices of Lawyers",
                "level": 6,
            },
            "region": ["EU"],
        },
        "role": {
            "function_code": "Legal & Compliance",
            "role_code": "AIA-P",
            "role_title": "Legal Lead",
            "objectives": [],
        },
    }

    result = normalize_context_role(v3_payload)

    # Should use provided region
    assert result["sector_profile"]["region"] == ["EU"]
    assert "EU_AI_Act" in result["sector_profile"]["regulatory"]
    assert "GDPR" in result["sector_profile"]["regulatory"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
