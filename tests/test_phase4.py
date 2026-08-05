"""Tests for deterministic start-node sampling and latency summaries."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics.latency import summarize_latencies
from src.utils.sampling import select_start_nodes


def test_start_node_selection_is_reproducible():
    nodes = list(range(1, 1001))
    a = select_start_nodes(nodes, count=100, seed=42)
    b = select_start_nodes(nodes, count=100, seed=42)
    c = select_start_nodes(nodes, count=100, seed=7)
    assert a == b
    assert a != c
    assert len(a) == 100
    assert a == sorted(a)


def test_summarize_latencies_includes_required_percentiles():
    values = [float(i) for i in range(1, 101)]
    stats = summarize_latencies(values)
    assert stats["count"] == 100
    assert stats["p50_ms"] == 50.5
    assert stats["p95_ms"] == 95.05
    assert "p99_ms" in stats
    assert "std_ms" in stats
