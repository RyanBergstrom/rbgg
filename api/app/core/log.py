"""Centralized trace logging for the rbgg backend.

Enabled when the RBGG_DEV environment variable is set to "true" or "1".
Logs only the submitted move and the screen state returned to the UI.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
from typing import Any

_logger: logging.Logger | None = None

_suppress_tracing: bool = False


def _is_dev() -> bool:
    """Check RBGG_DEV at runtime, not import time."""
    return os.environ.get("RBGG_DEV", "").lower() in ("true", "1")


@contextlib.contextmanager
def suppress_tracing():
    """Context manager to temporarily disable trace logging."""
    global _suppress_tracing
    _suppress_tracing = True
    try:
        yield
    finally:
        _suppress_tracing = False


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    _logger = logging.getLogger("rbgg")
    if _is_dev() and not _logger.handlers:
        log_path = os.environ.get("RBGG_LOG_FILE", "rbgg.log")
        handler = logging.FileHandler(log_path, encoding="utf-8", delay=True)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        ))
        _logger.addHandler(handler)
        _logger.setLevel(logging.DEBUG)
    return _logger


def trace(source: str, label: str, **kwargs) -> None:
    """Emit a trace log line if DEV mode is enabled."""
    if not _is_dev():
        return
    logger = _get_logger()
    logger.debug(f"[{source}] {label} {json.dumps(kwargs, separators=(',', ':'))}")


def trace_move(source: str, label: str, move: dict | None = None, **kwargs) -> None:
    """Log a move dict."""
    if not _is_dev():
        return
    logger = _get_logger()
    payload = {}
    if move:
        payload["move"] = move
    payload.update(kwargs)
    logger.debug(f"[{source}] {label} {json.dumps(payload, separators=(',', ':'))}")


def trace_api(source: str, label: str, **kwargs) -> None:
    """Log an API call."""
    if not _is_dev():
        return
    logger = _get_logger()
    logger.debug(f"[{source}] {label} {json.dumps(kwargs, separators=(',', ':'))}")
