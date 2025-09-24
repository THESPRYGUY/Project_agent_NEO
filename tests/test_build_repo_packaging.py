from __future__ import annotations

from pathlib import Path

import pytest

from neo_agent.server import build_repo

from tests._profile_factory import DEFAULT_OPTIONS, make_profile


def test_build_repository_with_git(monkeypatch, tmp_path):
    calls: list[Path] = []

    def fake_git(path: Path) -> None:
        calls.append(path)

    monkeypatch.setattr(build_repo, "git_init", fake_git)
    profile = make_profile()
    options = dict(DEFAULT_OPTIONS)
    options.update({"git_init": True, "zip": True})

    result = build_repo.build_repository(profile, options, output_root=tmp_path)
    repo_dir = Path(result["repo_path"])
    zip_path = Path(result["zip_path"])

    assert calls == [repo_dir]
    assert zip_path.exists()
    assert zip_path.stat().st_size > 0

    # Ensure manifest hash matches the file on disk
    manifest_disk = (repo_dir / "manifest.json").read_text(encoding="utf-8")
    assert "manifest_sha" in manifest_disk


def test_plan_respects_abort_policy(tmp_path):
    profile = make_profile()
    options = dict(DEFAULT_OPTIONS)
    result = build_repo.build_repository(profile, options, output_root=tmp_path)
    repo_dir = Path(result["repo_path"])
    manifest = (repo_dir / "manifest.json").read_text(encoding="utf-8")
    assert manifest

    options_aborted = dict(DEFAULT_OPTIONS)
    options_aborted["overwrite"] = "abort"
    target_file = repo_dir / "10_Prompt-Pack_v2.json"
    target_file.write_text("changed", encoding="utf-8")
    with pytest.raises(Exception):
        build_repo.plan_repository(profile, options_aborted, output_root=tmp_path)
