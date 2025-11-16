"""Logging helpers shared across the CV Tailor app."""
from __future__ import annotations

import contextvars
import logging
import os


def truthy(value: str | None) -> bool:
    """Return True if the provided env-style string is truthy."""

    if value is None:
        return False
    return value.strip().lower() not in {"", "0", "false", "off", "no"}


DEBUG_ENABLED = truthy(os.getenv("CV_TAILOR_DEBUG"))

_REQUEST_ID = contextvars.ContextVar("cv_tailor_request_id", default="-")
_LOGGING_INITIALIZED = False


def configure_logging() -> None:
    """Ensure logging has a baseline configuration."""

    global _LOGGING_INITIALIZED
    if _LOGGING_INITIALIZED:
        return

    level = logging.DEBUG if DEBUG_ENABLED else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _LOGGING_INITIALIZED = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger for CV Tailor."""

    return logging.getLogger(f"cv_tailor.{name}")


def set_request_id(request_id: str):
    """Set the active request id in a context variable."""

    return _REQUEST_ID.set(request_id)


def reset_request_id(token) -> None:
    """Reset the context variable to the previous request id."""

    _REQUEST_ID.reset(token)


def get_request_id() -> str:
    return _REQUEST_ID.get()


def format_with_request(message: str) -> str:
    """Prefix the message with the active request id for logging."""

    return f"[req={get_request_id()}] {message}"
