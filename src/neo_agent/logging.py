"""Structured logging helpers for Project NEO."""

from __future__ import annotations

import logging
from logging import Logger
from typing import Dict

_LOGGER_NAME = "neo_agent"


def get_logger(name: str | None = None) -> Logger:
    """Return a module level logger configured for structured output."""

    logger_name = f"{_LOGGER_NAME}.{name}" if name else _LOGGER_NAME
    logger = logging.getLogger(logger_name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def log_event(logger: Logger, event: str, payload: Dict[str, object] | None = None) -> None:
    """Log an event payload in a consistent format."""

    payload = payload or {}
    logger.info("event=%s payload=%s", event, payload)
