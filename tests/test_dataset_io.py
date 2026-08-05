"""Tests for dataset I/O helpers."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.dataset_io import batched


def test_batched_splits_evenly():
    items = [{"i": i} for i in range(5)]
    batches = list(batched(items, 2))
    assert len(batches) == 3
    assert batches[0] == [{"i": 0}, {"i": 1}]
    assert batches[-1] == [{"i": 4}]


def test_assert_safe_rel_type_accepts_cites():
    from src.adapters.cognodb import CognoDBAdapter

    CognoDBAdapter._assert_safe_rel_type("CITES")
