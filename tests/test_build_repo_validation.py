from __future__ import annotations

import pytest

from neo_agent.server.build_repo import plan_repository
from neo_agent.server.validators import validate_profile

from tests._profile_factory import DEFAULT_OPTIONS, make_profile


def test_validate_profile_success():
    profile = make_profile()
    issues = validate_profile(profile)
    assert issues == []


def test_validate_profile_failure_missing_persona():
    profile = make_profile(persona={"name": ""})
    issues = validate_profile(profile)
    assert any(issue.code == "E_SCHEMA_PERSONA_NAME" for issue in issues)


def test_plan_repository_requires_valid_profile(tmp_path):
    profile = make_profile()
    options = dict(DEFAULT_OPTIONS)
    plan = plan_repository(profile, options, output_root=tmp_path)
    assert plan["plan"]["inputs_sha256"]
    files = plan["plan"]["files"]
    assert len(files) == 22  # 20 pack files + README + manifest

    bad_profile = make_profile(domain={})
    with pytest.raises(Exception):
        plan_repository(bad_profile, options, output_root=tmp_path)
