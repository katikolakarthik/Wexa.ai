"""Shared timed workload execution helpers."""

from __future__ import annotations

import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import uuid4

from src.metrics.latency import summarize_latencies
from src.metrics.throughput import ops_per_second


@dataclass
class TimedOpResult:
    latency_ms: float
    success: bool
    error: str = ""
    start_node: Any = ""
    op_type: str = "read"
    iteration: int = 0
    payload: Any = None


@dataclass
class WorkloadOutcome:
    workload: str
    raw_rows: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


def time_call(fn: Callable[[], Any]) -> TimedOpResult:
    start = time.perf_counter_ns()
    try:
        payload = fn()
        latency_ms = (time.perf_counter_ns() - start) / 1_000_000.0
        return TimedOpResult(latency_ms=latency_ms, success=True, payload=payload)
    except Exception as exc:  # noqa: BLE001 — record all query failures
        latency_ms = (time.perf_counter_ns() - start) / 1_000_000.0
        return TimedOpResult(
            latency_ms=latency_ms,
            success=False,
            error=f"{type(exc).__name__}: {exc}",
            payload=None,
        )


def run_warmup_and_measure(
    *,
    database: str,
    workload: str,
    start_nodes: list[int],
    warmup_iterations: int,
    measured_iterations: int,
    operation: Callable[[int], Any],
    concurrency: int | str = "",
    op_type: str = "read",
) -> WorkloadOutcome:
    """Warm up, then measure one operation per start node iteration."""
    outcome = WorkloadOutcome(workload=workload)
    if measured_iterations > len(start_nodes):
        raise ValueError(
            f"{workload}: measured_iterations={measured_iterations} exceeds "
            f"start node list size={len(start_nodes)}"
        )

    for i in range(warmup_iterations):
        node_id = start_nodes[i % len(start_nodes)]
        timed = time_call(lambda n=node_id: operation(n))
        if not timed.success:
            outcome.failures.append(f"warmup {workload} iter={i}: {timed.error}")

    raw_rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    errors = 0
    wall_start = time.perf_counter_ns()

    for i in range(measured_iterations):
        node_id = start_nodes[i]
        timed = time_call(lambda n=node_id: operation(n))
        row = {
            "database": database,
            "workload": workload,
            "iteration": i,
            "start_node": node_id,
            "latency_ms": round(timed.latency_ms, 6),
            "success": timed.success,
            "error": timed.error,
            "concurrency": concurrency,
            "op_type": op_type,
        }
        raw_rows.append(row)
        if timed.success:
            latencies.append(timed.latency_ms)
        else:
            errors += 1
            outcome.failures.append(f"{workload} iter={i} node={node_id}: {timed.error}")

    wall_ms = (time.perf_counter_ns() - wall_start) / 1_000_000.0
    stats = summarize_latencies(latencies)
    successful = int(stats["count"])
    outcome.raw_rows = raw_rows
    outcome.summary = {
        "database": database,
        "workload": workload,
        "count": successful,
        "p50_ms": stats["p50_ms"],
        "p95_ms": stats["p95_ms"],
        "p99_ms": stats["p99_ms"],
        "mean_ms": stats["mean_ms"],
        "std_ms": stats["std_ms"],
        "min_ms": stats["min_ms"],
        "max_ms": stats["max_ms"],
        "throughput_qps": ops_per_second(successful, wall_ms),
        "errors": errors,
        "concurrency": concurrency,
        "successful_ops": successful,
        "failed_ops": errors,
        "wall_clock_ms": round(wall_ms, 3),
        "read_throughput_qps": "",
        "write_throughput_qps": "",
    }
    return outcome


def run_aggregation_workload(
    *,
    database: str,
    warmup_iterations: int,
    measured_iterations: int,
    operation: Callable[[], Any],
) -> WorkloadOutcome:
    outcome = WorkloadOutcome(workload="aggregation")

    for i in range(warmup_iterations):
        timed = time_call(operation)
        if not timed.success:
            outcome.failures.append(f"warmup aggregation iter={i}: {timed.error}")

    raw_rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    errors = 0
    wall_start = time.perf_counter_ns()

    for i in range(measured_iterations):
        timed = time_call(operation)
        row = {
            "database": database,
            "workload": "aggregation",
            "iteration": i,
            "start_node": "",
            "latency_ms": round(timed.latency_ms, 6),
            "success": timed.success,
            "error": timed.error,
            "concurrency": "",
            "op_type": "read",
        }
        raw_rows.append(row)
        if timed.success:
            latencies.append(timed.latency_ms)
        else:
            errors += 1
            outcome.failures.append(f"aggregation iter={i}: {timed.error}")

    wall_ms = (time.perf_counter_ns() - wall_start) / 1_000_000.0
    stats = summarize_latencies(latencies)
    successful = int(stats["count"])
    outcome.raw_rows = raw_rows
    outcome.summary = {
        "database": database,
        "workload": "aggregation",
        "count": successful,
        "p50_ms": stats["p50_ms"],
        "p95_ms": stats["p95_ms"],
        "p99_ms": stats["p99_ms"],
        "mean_ms": stats["mean_ms"],
        "std_ms": stats["std_ms"],
        "min_ms": stats["min_ms"],
        "max_ms": stats["max_ms"],
        "throughput_qps": ops_per_second(successful, wall_ms),
        "errors": errors,
        "concurrency": "",
        "successful_ops": successful,
        "failed_ops": errors,
        "wall_clock_ms": round(wall_ms, 3),
        "read_throughput_qps": "",
        "write_throughput_qps": "",
    }
    return outcome


def run_mixed_workload(
    *,
    database: str,
    start_nodes: list[int],
    concurrency: int,
    total_ops: int,
    read_ratio: float,
    read_op: Callable[[int], Any],
    write_op: Callable[[dict[str, Any]], Any],
    seed: int,
) -> WorkloadOutcome:
    """Concurrent mixed read/write using temporary write targets."""
    import random

    workload = f"mixed_c{concurrency}"
    outcome = WorkloadOutcome(workload=workload)
    rng = random.Random(seed + concurrency)

    # Precompute the schedule so determinism does not depend on thread timing.
    schedule: list[tuple[str, Any]] = []
    for iteration in range(total_ops):
        if rng.random() < read_ratio:
            schedule.append(("read", start_nodes[iteration % len(start_nodes)]))
        else:
            schedule.append(
                (
                    "write",
                    {
                        "temp_id": f"bench-{concurrency}-{iteration}-{uuid4().hex}",
                        "worker_id": concurrency,
                    },
                )
            )

    def one_op(iteration: int, op_type: str, arg: Any) -> TimedOpResult:
        if op_type == "read":
            timed = time_call(lambda: read_op(int(arg)))
            timed.start_node = arg
        else:
            timed = time_call(lambda: write_op(arg))
            timed.start_node = ""
        timed.op_type = op_type
        timed.iteration = iteration
        return timed

    raw_rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    errors = 0
    success_reads = 0
    success_writes = 0
    wall_start = time.perf_counter_ns()

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(one_op, i, op_type, arg)
            for i, (op_type, arg) in enumerate(schedule)
        ]
        for future in as_completed(futures):
            try:
                timed = future.result()
            except Exception as exc:  # noqa: BLE001
                errors += 1
                outcome.failures.append(
                    f"{workload} future error: {type(exc).__name__}: {exc}\n"
                    f"{traceback.format_exc()}"
                )
                continue

            row = {
                "database": database,
                "workload": workload,
                "iteration": timed.iteration,
                "start_node": timed.start_node,
                "latency_ms": round(timed.latency_ms, 6),
                "success": timed.success,
                "error": timed.error,
                "concurrency": concurrency,
                "op_type": timed.op_type,
            }
            raw_rows.append(row)
            if timed.success:
                latencies.append(timed.latency_ms)
                if timed.op_type == "read":
                    success_reads += 1
                else:
                    success_writes += 1
            else:
                errors += 1
                outcome.failures.append(
                    f"{workload} iter={timed.iteration}: {timed.error}"
                )

    wall_ms = (time.perf_counter_ns() - wall_start) / 1_000_000.0
    stats = summarize_latencies(latencies)
    successful = success_reads + success_writes
    outcome.raw_rows = sorted(raw_rows, key=lambda r: int(r["iteration"]))
    outcome.summary = {
        "database": database,
        "workload": workload,
        "count": successful,
        "p50_ms": stats["p50_ms"],
        "p95_ms": stats["p95_ms"],
        "p99_ms": stats["p99_ms"],
        "mean_ms": stats["mean_ms"],
        "std_ms": stats["std_ms"],
        "min_ms": stats["min_ms"],
        "max_ms": stats["max_ms"],
        "throughput_qps": ops_per_second(successful, wall_ms),
        "errors": errors,
        "concurrency": concurrency,
        "successful_ops": successful,
        "failed_ops": errors,
        "wall_clock_ms": round(wall_ms, 3),
        "read_throughput_qps": ops_per_second(success_reads, wall_ms),
        "write_throughput_qps": ops_per_second(success_writes, wall_ms),
    }
    return outcome
