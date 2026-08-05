"""Unit tests for dataset preparation (no network if fixtures provided)."""

from __future__ import annotations

import gzip
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dataset.prepare import read_edges_from_gz, subsample_edges


def _write_sample_gz(path: Path) -> None:
    content = """# Directed graph: sample
# FromNodeId\tToNodeId
1 2
1 3
2 3
2 3
3 3
4 1
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(content)


def test_read_edges_removes_duplicates_and_self_loops(tmp_path: Path):
    raw = tmp_path / "sample.txt.gz"
    _write_sample_gz(raw)
    edges, self_loops, duplicates = read_edges_from_gz(raw)
    assert edges == [(1, 2), (1, 3), (2, 3), (4, 1)]
    assert self_loops == 1
    assert duplicates == 1


def test_subsample_edges_is_deterministic():
    edges = [(i, i + 1) for i in range(1000)]
    a = subsample_edges(edges, max_relationships=399, seed=42)
    b = subsample_edges(edges, max_relationships=399, seed=42)
    c = subsample_edges(edges, max_relationships=399, seed=7)
    assert len(a) == 399
    assert a == b
    assert a != c
    # Selected edges keep original relative order.
    assert a == sorted(a, key=lambda e: edges.index(e))
