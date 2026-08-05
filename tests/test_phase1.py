"""Unit tests that do not require live cloud credentials."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics.latency import percentile
from src.utils.config import load_benchmark_config
from src.adapters.base import GraphDatabaseAdapter
from src.adapters.cognodb import CognoDBAdapter


def test_percentile_basic():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile(values, 50) == 3.0
    assert percentile(values, 0) == 1.0
    assert percentile(values, 100) == 5.0


def test_percentile_empty_raises():
    with pytest.raises(ValueError):
        percentile([], 50)


def test_load_benchmark_config():
    cfg = load_benchmark_config()
    assert cfg["random_seed"] == 42
    assert cfg["warmup_iterations"] == 20
    assert cfg["measured_iterations"] == 100
    assert cfg["concurrency_levels"] == [1, 10, 40]
    assert cfg["resources"]["cognodb"]["ram_mb"] == 512


def test_cognodb_adapter_implements_interface():
    assert issubclass(CognoDBAdapter, GraphDatabaseAdapter)
    adapter = CognoDBAdapter(uri="bolt://example", username="u", password="p")
    assert adapter.name == "cognodb"


def test_cognodb_missing_credentials_raises():
    adapter = CognoDBAdapter(uri="", username="", password="")
    with pytest.raises(ValueError) as exc:
        adapter.connect()
    message = str(exc.value)
    assert "COGNODB_URI" in message
    assert "COGNODB_PASSWORD" in message
