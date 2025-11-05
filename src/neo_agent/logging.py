"""Structured JSON logging helpers for Project NEO."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from logging import Logger
from typing import Dict

_LOGGER_NAME = "neo_agent"


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        payload = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Optional extras often used in this codebase
        if hasattr(record, "event"):
            payload["event"] = getattr(record, "event")
        if hasattr(record, "payload"):
            payload["payload"] = getattr(record, "payload")
        # Observability context (when provided by middleware or callers)
        for key in ("req_id", "method", "path", "status", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str | None = None) -> Logger:
    """Return a module level logger configured for structured JSON output."""

    logger_name = f"{_LOGGER_NAME}.{name}" if name else _LOGGER_NAME
    logger = logging.getLogger(logger_name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        # Honor LOG_LEVEL env, default INFO
        level = os.environ.get("LOG_LEVEL", "INFO").upper()
        try:
            logger.setLevel(getattr(logging, level, logging.INFO))
        except Exception:
            logger.setLevel(logging.INFO)
    return logger


def log_event(
    logger: Logger, event: str, payload: Dict[str, object] | None = None
) -> None:
    """Log an event payload in a consistent JSON format."""

    payload = payload or {}
    # Attach fields for the formatter to include
    extra = {"event": event, "payload": payload}
    logger.info(f"event={event}", extra=extra)
