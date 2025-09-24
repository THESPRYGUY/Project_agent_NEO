"""Manifest helpers for generated agent repositories."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping


def _sha256_bytes(data: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(data)
    return digest.hexdigest()


def make_manifest(build_ctx: Mapping[str, object], outputs: Iterable[tuple[Path, bytes]]) -> dict:
    inputs_hash = str(build_ctx.get("inputs_sha256", ""))
    profile_id = str(build_ctx.get("profile_id", ""))
    generated_at = str(build_ctx.get("generated_at", ""))
    files = []
    for path, content in outputs:
        files.append({"path": path.name, "sha256": _sha256_bytes(content)})
    files.sort(key=lambda item: item["path"])
    manifest = {
        "version": "v2.0.0",
        "profile_id": profile_id,
        "inputs_sha256": inputs_hash,
        "generated_at": generated_at,
        "files": files,
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode("utf-8")
    manifest_sha = _sha256_bytes(manifest_bytes)
    manifest["manifest_sha"] = manifest_sha
    manifest_file_bytes = json.dumps(manifest, sort_keys=True).encode("utf-8")
    manifest["files"].append({"path": "manifest.json", "sha256": _sha256_bytes(manifest_file_bytes)})
    manifest["files"].sort(key=lambda item: item["path"])
    return manifest
