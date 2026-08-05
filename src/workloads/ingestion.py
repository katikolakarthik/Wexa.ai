"""Ingestion timing helpers."""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any


def elapsed_ms(start_ns: int, end_ns: int | None = None) -> float:
    end = time.perf_counter_ns() if end_ns is None else end_ns
    return (end - start_ns) / 1_000_000.0


def throughput_per_second(count: int, duration_ms: float) -> float:
    if duration_ms <= 0:
        return 0.0
    return count / (duration_ms / 1000.0)


def write_ingestion_result(path: Path, row: dict[str, Any]) -> None:
    """Overwrite ingestion summary CSV with the latest run (one row)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "database",
        "batch_size",
        "nodes_inserted",
        "relationships_inserted",
        "node_load_ms",
        "relationship_load_ms",
        "total_ingestion_ms",
        "nodes_per_second",
        "relationships_per_second",
        "verified_node_count",
        "verified_relationship_count",
        "counts_match",
        "success",
        "error",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in fieldnames})
