"""Raw/processed result writers."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


RAW_LATENCY_FIELDS = [
    "database",
    "workload",
    "iteration",
    "start_node",
    "latency_ms",
    "success",
    "error",
    "concurrency",
    "op_type",
]

SUMMARY_FIELDS = [
    "database",
    "workload",
    "count",
    "p50_ms",
    "p95_ms",
    "p99_ms",
    "mean_ms",
    "std_ms",
    "min_ms",
    "max_ms",
    "throughput_qps",
    "errors",
    "concurrency",
    "successful_ops",
    "failed_ops",
    "wall_clock_ms",
    "read_throughput_qps",
    "write_throughput_qps",
]


def write_raw_latency_rows(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_LATENCY_FIELDS)
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in RAW_LATENCY_FIELDS})


def write_summary_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in SUMMARY_FIELDS})
