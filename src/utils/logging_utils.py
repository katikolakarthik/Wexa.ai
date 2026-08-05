"""Logging helpers that never emit secrets."""

from __future__ import annotations

import logging
import re
from typing import Iterable

_SECRET_PATTERNS = (
    re.compile(r"(password\s*[=:]\s*)(\S+)", re.IGNORECASE),
    re.compile(r"(passwd\s*[=:]\s*)(\S+)", re.IGNORECASE),
    re.compile(r"(pwd\s*[=:]\s*)(\S+)", re.IGNORECASE),
    re.compile(r"(://[^:/@]+):([^@]+)@", re.IGNORECASE),
)

_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
    }
)


def redact_secrets(text: str) -> str:
    """Best-effort redaction for accidental credential leakage in log strings."""
    redacted = text
    redacted = re.sub(
        r"(://[^:/@]+):([^@]+)@",
        r"\1:***@",
        redacted,
        flags=re.IGNORECASE,
    )
    for pattern in (
        re.compile(r"(password\s*[=:]\s*)(\S+)", re.IGNORECASE),
        re.compile(r"(passwd\s*[=:]\s*)(\S+)", re.IGNORECASE),
        re.compile(r"(pwd\s*[=:]\s*)(\S+)", re.IGNORECASE),
    ):
        redacted = pattern.sub(r"\1***", redacted)
    return redacted


def sanitize_mapping(data: dict, sensitive_keys: Iterable[str] | None = None) -> dict:
    """Return a shallow copy with sensitive keys replaced by '***'."""
    keys = {k.lower() for k in (sensitive_keys or _SENSITIVE_KEYS)}
    return {
        key: ("***" if str(key).lower() in keys else value)
        for key, value in data.items()
    }


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure root project logger."""
    logger = logging.getLogger("cognodb_benchmark")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger
