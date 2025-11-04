"""Adapter facade for legacy callers that expect ``RepoBuilder``.

This module bridges older build flows onto the canonical ``write_repo_files``
routine while guaranteeing that ``_generated/_last_build.json`` is refreshed for
each build invocation.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from .writers import write_repo_files

DEFAULT_BUILD_ROOT = Path("generated_repos") / "agent-build-007-2-1-1"
DEFAULT_GENERATED_ROOT = Path("_generated")

_SLUG_RE = re.compile(r"[^a-z0-9\-]+")


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _slugify(value: str) -> str:
    value = value.strip().lower().replace("_", "-")
    value = _SLUG_RE.sub("-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-")


class RepoBuilder:
    """Minimal adapter that orchestrates repo writes via ``write_repo_files``."""

    def __init__(
        self,
        base_dir: str | Path | None = None,
        *,
        generated_root: str | Path | None = None,
        build_root: str | Path | None = None,
        build_id: str | None = None,
        schema_version: str | None = None,
        **config: Any,
    ) -> None:
        base_path = Path(base_dir) if base_dir is not None else Path.cwd()
        self.base_dir = base_path.resolve()

        gen_root = Path(generated_root) if generated_root is not None else DEFAULT_GENERATED_ROOT
        if not gen_root.is_absolute():
            gen_root = self.base_dir / gen_root
        self.generated_root = gen_root
        self.generated_root.mkdir(parents=True, exist_ok=True)

        build_root_path = Path(build_root) if build_root is not None else DEFAULT_BUILD_ROOT
        if not build_root_path.is_absolute():
            build_root_path = self.generated_root / build_root_path
        self.build_root = build_root_path
        self.build_root.mkdir(parents=True, exist_ok=True)

        self.build_id = build_id or uuid.uuid4().hex[:8]
        self.schema_version = schema_version or "2.1.1"
        self.config: dict[str, Any] = {
            "build_id": self.build_id,
            "schema_version": self.schema_version,
            **config,
        }

        self._seen_slugs: set[str] = set()

    def build(
        self,
        profile: Mapping[str, Any],
        *,
        slug: str | None = None,
        out_dir: str | Path | None = None,
        schema_version: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(profile, Mapping):
            raise TypeError("profile must be a mapping")

        repo_dir = self._resolve_repo_dir(profile, slug=slug, out_dir=out_dir)
        packs = write_repo_files(profile, repo_dir)

        last_build_path = self._sync_last_build_pointer(
            repo_dir=repo_dir,
            packs=packs,
            profile=profile,
            schema_version=schema_version,
        )

        return {
            "outdir": str(repo_dir.resolve()),
            "packs": packs,
            "pack_count": len(packs),
            "last_build_path": str(last_build_path),
        }

    def generate_repo(
        self,
        output_dir: str | Path,
        *,
        profile: Mapping[str, Any] | None = None,
        slug: str | None = None,
    ) -> dict[str, Any]:
        """Compat wrapper expected by legacy tests."""

        repo_dir = Path(output_dir)
        repo_dir.mkdir(parents=True, exist_ok=True)

        merged_profile: dict[str, Any] = {}
        merged_profile.update(self.config)
        if profile:
            merged_profile.update(dict(profile))

        return self.build(merged_profile, slug=slug, out_dir=repo_dir)

    def _resolve_repo_dir(
        self,
        profile: Mapping[str, Any],
        *,
        slug: str | None,
        out_dir: str | Path | None,
    ) -> Path:
        if out_dir is not None:
            out_path = Path(out_dir)
            return out_path if out_path.is_absolute() else (self.base_dir / out_path)

        candidate = slug or self._derive_slug(profile)
        unique = self._ensure_unique_slug(candidate)
        return (self.build_root / unique).resolve()

    def _derive_slug(self, profile: Mapping[str, Any]) -> str:
        agent = _as_mapping(profile.get("agent"))
        identity = _as_mapping(profile.get("identity"))
        fallback = identity.get("agent_id") or agent.get("name") or uuid.uuid4().hex[:8]

        pieces = [
            str(agent.get("name") or "").strip(),
            str(agent.get("version") or "").strip(),
        ]
        slug = _slugify("-".join([p for p in pieces if p]))
        if not slug:
            slug = _slugify(str(fallback))
        if not slug:
            slug = uuid.uuid4().hex[:8]
        return slug

    def _ensure_unique_slug(self, base_slug: str) -> str:
        slug = base_slug
        index = 2
        while not slug or slug in self._seen_slugs or (self.build_root / slug).exists():
            slug = f"{base_slug}-{index}"
            index += 1
        self._seen_slugs.add(slug)
        return slug

    def _sync_last_build_pointer(
        self,
        *,
        repo_dir: Path,
        packs: Mapping[str, Any],
        profile: Mapping[str, Any],
        schema_version: str | None,
    ) -> Path:
        pointer_dst = self.generated_root / "_last_build.json"
        pointer_dst.parent.mkdir(parents=True, exist_ok=True)

        pointer_src: Path | None = None
        parents = list(repo_dir.parents)
        if len(parents) >= 2:
            candidate = parents[1] / "_last_build.json"
            if candidate.exists():
                pointer_src = candidate

        payload: MutableMapping[str, Any] | None = None
        if pointer_src:
            try:
                payload = json.loads(pointer_src.read_text(encoding="utf-8"))
            except Exception:
                payload = None

        if payload is None:
            payload = {
                "schema_version": str(
                    schema_version or profile.get("schema_version") or self.schema_version
                ),
                "status": "complete",
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "outdir": str(repo_dir.resolve()),
                "files": len(packs),
                "build_id": profile.get("build_id") or self.build_id or repo_dir.name,
            }
            commit_hint = profile.get("commit") or profile.get("build_commit")
            if commit_hint:
                payload["commit"] = str(commit_hint)
        else:
            payload = dict(payload)
            payload["outdir"] = str(repo_dir.resolve())

        text_payload = json.dumps(payload, indent=2)
        pointer_dst.write_text(text_payload, encoding="utf-8")

        try:
            base_generated = (self.base_dir / "_generated").resolve()
            if base_generated != self.generated_root.resolve():
                base_generated.mkdir(parents=True, exist_ok=True)
                (base_generated / "_last_build.json").write_text(text_payload, encoding="utf-8")
        except Exception:
            pass

        return pointer_dst


__all__ = ["RepoBuilder"]
