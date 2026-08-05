"""Tests for secret redaction helpers."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.logging_utils import redact_secrets, sanitize_mapping


def test_redact_password_assignment():
    text = "login failed password=super-secret"
    assert "super-secret" not in redact_secrets(text)
    assert "***" in redact_secrets(text)


def test_redact_uri_userinfo():
    text = "bolt+s://user:hunter2@example.com:7687"
    out = redact_secrets(text)
    assert "hunter2" not in out
    assert "example.com" in out


def test_sanitize_mapping():
    data = {"username": "alice", "password": "secret", "uri": "bolt://x"}
    clean = sanitize_mapping(data)
    assert clean["username"] == "alice"
    assert clean["password"] == "***"
