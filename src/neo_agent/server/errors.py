"""Typed exceptions and shared error metadata for repo generation APIs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping


@dataclass(slots=True)
class ErrorMetadata:
    """Metadata describing an error response."""

    code: str
    hint: str
    doc_ref: str | None = None


class ServerError(Exception):
    """Base class for structured server exceptions."""

    stage: str = "unknown"

    def __init__(self, code: str, message: str, *, hint: str | None = None, doc_ref: str | None = None, stage: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.hint = hint
        self.doc_ref = doc_ref
        if stage:
            self.stage = stage

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "stage": self.stage,
            "hint": self.hint,
            "doc_ref": self.doc_ref,
        }


class SchemaValidationError(ServerError):
    stage = "validate"


class TemplateRenderError(ServerError):
    stage = "render"


class PackagingError(ServerError):
    stage = "package"


ERROR_MAP: Mapping[str, ErrorMetadata] = {
    "E_SCHEMA_INVALID_PROFILE": ErrorMetadata(
        code="E_SCHEMA_INVALID_PROFILE",
        hint="Profile failed validation. Review issues and try again.",
        doc_ref="https://project-neo.local/docs/build#profile",
    ),
    "E_SCHEMA_INVALID_OPTIONS": ErrorMetadata(
        code="E_SCHEMA_INVALID_OPTIONS",
        hint="Build options are not valid.",
        doc_ref="https://project-neo.local/docs/build#options",
    ),
    "E_TEMPLATE_RENDER": ErrorMetadata(
        code="E_TEMPLATE_RENDER",
        hint="Template rendering failed during repo generation.",
        doc_ref="https://project-neo.local/docs/build#templates",
    ),
    "E_IO_WRITE": ErrorMetadata(
        code="E_IO_WRITE",
        hint="Failed to write generated files to disk.",
        doc_ref="https://project-neo.local/docs/build#filesystem",
    ),
    "E_ZIP_FAIL": ErrorMetadata(
        code="E_ZIP_FAIL",
        hint="Packaging ZIP archive failed.",
        doc_ref="https://project-neo.local/docs/build#packaging",
    ),
    "E_GIT_INIT": ErrorMetadata(
        code="E_GIT_INIT",
        hint="Git initialization failed during packaging stage.",
        doc_ref="https://project-neo.local/docs/build#git",
    ),
}


def enrich_error(code: str, message: str, *, stage: str | None = None) -> ServerError:
    meta = ERROR_MAP.get(code)
    hint = meta.hint if meta else None
    doc_ref = meta.doc_ref if meta else None
    exc_cls: type[ServerError]
    if stage == "render":
        exc_cls = TemplateRenderError
    elif stage == "package":
        exc_cls = PackagingError
    else:
        exc_cls = SchemaValidationError if code.startswith("E_SCHEMA") else ServerError
    return exc_cls(code, message, hint=hint, doc_ref=doc_ref, stage=stage)
