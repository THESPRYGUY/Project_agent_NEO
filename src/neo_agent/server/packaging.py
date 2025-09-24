"""Packaging helpers for generated repositories."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .errors import PackagingError, enrich_error


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def package_zip(source_dir: Path, zip_path: Path) -> Path:
    try:
        ensure_directory(zip_path.parent)
        with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
            for file_path in sorted(source_dir.rglob("*")):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(source_dir))
        return zip_path
    except Exception as exc:  # pragma: no cover - defensive guard
        raise enrich_error("E_ZIP_FAIL", str(exc), stage="package") from exc


def git_init(repo_dir: Path) -> None:
    try:
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as exc:  # pragma: no cover - git missing
        raise PackagingError("E_GIT_INIT", "git executable not available", stage="package") from exc
    except subprocess.CalledProcessError as exc:  # pragma: no cover - git failure
        raise PackagingError("E_GIT_INIT", f"git command failed: {exc.stderr}", stage="package") from exc


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
