from __future__ import annotations

from pathlib import Path

from neo_agent.server.build_repo import build_repository

from tests._profile_factory import DEFAULT_OPTIONS, make_profile


def test_build_repository_idempotent(tmp_path):
    profile = make_profile()
    options = dict(DEFAULT_OPTIONS)
    first = build_repository(profile, options, output_root=tmp_path)
    repo_dir = Path(first["repo_path"])
    assert repo_dir.exists()
    manifest_sha = first["manifest"]["manifest_sha"]

    second = build_repository(profile, options, output_root=tmp_path)
    assert second["manifest"]["manifest_sha"] == manifest_sha
    assert second["manifest"]["inputs_sha256"] == first["manifest"]["inputs_sha256"]
    assert (repo_dir / "manifest.json").exists()
    assert (repo_dir / "README_intro.md").exists()

    # Ensure no additional files were created beyond expected pack
    expected_files = {entry["path"] for entry in second["manifest"]["files"]}
    on_disk = {str(path.relative_to(repo_dir)) for path in repo_dir.glob("*") if path.is_file()}
    assert expected_files.issuperset(on_disk)
