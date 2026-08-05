"""Throughput helpers for mixed workloads."""

from __future__ import annotations


def ops_per_second(successful_ops: int, wall_clock_ms: float) -> float:
    if wall_clock_ms <= 0:
        return 0.0
    return successful_ops / (wall_clock_ms / 1000.0)
