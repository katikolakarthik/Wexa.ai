"""Latency metrics and distribution summaries."""

from __future__ import annotations

from typing import Sequence

import numpy as np


def percentile(values: Sequence[float], p: float) -> float:
    """Return the p-th percentile (0–100) using linear interpolation."""
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        raise ValueError("Cannot compute percentile of an empty sequence.")
    if not 0.0 <= p <= 100.0:
        raise ValueError(f"Percentile must be in [0, 100], got {p}.")
    return float(np.percentile(arr, p))


def summarize_latencies(values: Sequence[float]) -> dict[str, float | int]:
    """Compute count/min/mean/median/p50/p90/p95/p99/max/std for latencies in ms."""
    if not values:
        return {
            "count": 0,
            "min_ms": float("nan"),
            "mean_ms": float("nan"),
            "median_ms": float("nan"),
            "p50_ms": float("nan"),
            "p90_ms": float("nan"),
            "p95_ms": float("nan"),
            "p99_ms": float("nan"),
            "max_ms": float("nan"),
            "std_ms": float("nan"),
        }

    arr = np.asarray(values, dtype=float)
    return {
        "count": int(arr.size),
        "min_ms": float(np.min(arr)),
        "mean_ms": float(np.mean(arr)),
        "median_ms": float(np.median(arr)),
        "p50_ms": percentile(arr, 50),
        "p90_ms": percentile(arr, 90),
        "p95_ms": percentile(arr, 95),
        "p99_ms": percentile(arr, 99),
        "max_ms": float(np.max(arr)),
        "std_ms": float(np.std(arr, ddof=0)),
    }
