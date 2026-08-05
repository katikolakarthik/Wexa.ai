#!/usr/bin/env python3
"""Run benchmark workloads against one or more databases.

Examples:
  python scripts/run_benchmark.py --database cognodb
  python scripts/run_benchmark.py --database neo4j,memgraph
  python scripts/run_benchmark.py --database all --skip-missing
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.base import GraphDatabaseAdapter
from src.adapters.registry import (
    ALL_DATABASES,
    credential_status,
    get_adapter,
    resolve_databases,
)
from src.metrics.results_io import write_raw_latency_rows, write_summary_rows
from src.utils.config import load_benchmark_config
from src.utils.dataset_io import load_nodes_csv
from src.utils.sampling import load_start_nodes, save_start_nodes, select_start_nodes
from src.workloads.runner import (
    WorkloadOutcome,
    run_aggregation_workload,
    run_mixed_workload,
    run_warmup_and_measure,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run graph database workloads.")
    parser.add_argument(
        "--database",
        required=True,
        help=f"Database name, comma-list, or 'all'. Supported: {', '.join(ALL_DATABASES)}",
    )
    parser.add_argument(
        "--workloads",
        default="all",
        help="Comma list: traversal,lookup,aggregation,mixed,all",
    )
    parser.add_argument(
        "--skip-mixed",
        action="store_true",
        help="Skip concurrent mixed workloads.",
    )
    parser.add_argument(
        "--skip-missing",
        action="store_true",
        help="Skip databases missing credentials (implied for --database all).",
    )
    return parser.parse_args()


def ensure_start_nodes(cfg: dict, prepared_dir: Path) -> list[int]:
    seed = int(cfg["random_seed"])
    measured = int(cfg["measured_iterations"])
    warmup = int(cfg["warmup_iterations"])
    needed = max(measured, warmup)
    path = prepared_dir / "start_nodes.json"

    if path.is_file():
        nodes = load_start_nodes(path)
        if len(nodes) >= needed:
            return nodes

    nodes_csv = prepared_dir / cfg["dataset"]["nodes_file"]
    all_ids = [row["node_id"] for row in load_nodes_csv(nodes_csv)]
    count = max(needed, measured)
    selected = select_start_nodes(all_ids, count=count, seed=seed)
    save_start_nodes(path, selected, seed=seed)
    return selected


def print_summary(summary: dict) -> None:
    print(
        f"  {summary['workload']:<16} "
        f"n={summary['count']:<4} "
        f"p50={summary['p50_ms']!s:<12} "
        f"p95={summary['p95_ms']!s:<12} "
        f"errors={summary['errors']}"
    )


def run_one_database(
    *,
    db_name: str,
    selected_workloads: set[str],
    cfg: dict,
    start_nodes: list[int],
    raw_dir: Path,
    processed_dir: Path,
    prepared_dir: Path,
) -> int:
    warmup = int(cfg["warmup_iterations"])
    measured = int(cfg["measured_iterations"])
    seed = int(cfg["random_seed"])
    read_ratio = float(cfg.get("read_ratio", 0.8))
    concurrency_levels = list(cfg.get("concurrency_levels", [1, 10, 40]))

    print(f"\n======== {db_name} ========")
    print(f"Start nodes         : {len(start_nodes)} (seed={seed})")
    print(f"Warmup / measured   : {warmup} / {measured}")
    print(f"Workloads           : {', '.join(sorted(selected_workloads))}")

    adapter: GraphDatabaseAdapter = get_adapter(db_name)
    failures: list[str] = []
    summaries: list[dict] = []

    latency_path = raw_dir / f"{db_name}_latency.csv"
    mixed_path = raw_dir / f"{db_name}_mixed.csv"
    summary_path = processed_dir / "summary.csv"
    for path in (latency_path, mixed_path):
        if path.exists():
            path.unlink()

    try:
        adapter.connect()
        counts = adapter.get_counts()  # type: ignore[attr-defined]
        print(
            f"DB counts           : nodes={counts['nodes']:,} "
            f"relationships={counts['relationships']:,}"
        )
        if counts["nodes"] == 0:
            print("FAILURE: Database appears empty. Run load_data.py first.")
            return 1

        try:
            adapter.create_schema()
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: schema refresh failed: {exc}")

        def persist(outcome: WorkloadOutcome, *, mixed: bool = False) -> None:
            path = mixed_path if mixed else latency_path
            write_raw_latency_rows(path, outcome.raw_rows)
            summaries.append(outcome.summary)
            failures.extend(outcome.failures)
            print_summary(outcome.summary)

        if "traversal" in selected_workloads:
            print("\nTraversal workloads")
            for name, fn in (
                ("one_hop", adapter.one_hop),
                ("two_hop", adapter.two_hop),
                ("three_hop", adapter.three_hop),
            ):
                outcome = run_warmup_and_measure(
                    database=db_name,
                    workload=name,
                    start_nodes=start_nodes,
                    warmup_iterations=warmup,
                    measured_iterations=measured,
                    operation=fn,
                )
                persist(outcome)

        if "lookup" in selected_workloads:
            print("\nLookup workloads")
            outcome = run_warmup_and_measure(
                database=db_name,
                workload="point_lookup",
                start_nodes=start_nodes,
                warmup_iterations=warmup,
                measured_iterations=measured,
                operation=adapter.point_lookup,
            )
            persist(outcome)

            outcome = run_warmup_and_measure(
                database=db_name,
                workload="filtered_lookup",
                start_nodes=start_nodes,
                warmup_iterations=warmup,
                measured_iterations=measured,
                operation=lambda _node_id: adapter.filtered_lookup("label", "Paper"),
            )
            persist(outcome)

        if "aggregation" in selected_workloads:
            print("\nAggregation workload")
            outcome = run_aggregation_workload(
                database=db_name,
                warmup_iterations=warmup,
                measured_iterations=measured,
                operation=adapter.aggregation,
            )
            persist(outcome)

        if "mixed" in selected_workloads:
            print("\nMixed read/write workloads")
            print(f"  mix read/write     : {read_ratio:.0%} / {1 - read_ratio:.0%}")
            print(f"  concurrency levels : {concurrency_levels}")
            for level in concurrency_levels:
                total_ops = measured * max(1, int(level))
                outcome = run_mixed_workload(
                    database=db_name,
                    start_nodes=start_nodes,
                    concurrency=int(level),
                    total_ops=total_ops,
                    read_ratio=read_ratio,
                    read_op=adapter.mixed_read,
                    write_op=adapter.mixed_write,
                    seed=seed,
                )
                persist(outcome, mixed=True)

            if hasattr(adapter, "cleanup_benchmark_temp"):
                deleted = adapter.cleanup_benchmark_temp()  # type: ignore[attr-defined]
                print(f"  cleaned temp nodes : {deleted:,}")

        existing: list[dict] = []
        if summary_path.exists() and summary_path.stat().st_size > 0:
            with summary_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                existing = [row for row in reader if row.get("database") != db_name]
            summary_path.unlink()
        write_summary_rows(summary_path, existing + summaries)

        print("\nFailure summary")
        print("---------------")
        if failures:
            print(f"{len(failures)} failure(s) recorded:")
            for item in failures[:30]:
                print(f"  - {item}")
            if len(failures) > 30:
                print(f"  ... and {len(failures) - 30} more")
        else:
            print("No failures recorded.")

        print("\nArtifacts")
        print(f"  raw latency : {latency_path}")
        print(f"  raw mixed   : {mixed_path}")
        print(f"  summary     : {summary_path}")
        print(f"  start nodes : {prepared_dir / 'start_nodes.json'}")

        if summaries and all(int(s.get("successful_ops") or 0) == 0 for s in summaries):
            print("FAILURE: All workloads reported zero successful operations.")
            return 1

        print(f"SUCCESS: {db_name} workloads completed.")
        return 0 if not failures else 2

    except Exception as exc:  # noqa: BLE001
        print(f"FAILURE: Unexpected error ({type(exc).__name__}): {exc}")
        return 1
    finally:
        adapter.close()


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    cfg = load_benchmark_config()

    try:
        targets = resolve_databases(args.database)
    except ValueError as exc:
        print(f"FAILURE: {exc}")
        return 1

    selected_workloads = {
        part.strip().lower()
        for part in args.workloads.split(",")
        if part.strip()
    }
    if "all" in selected_workloads:
        selected_workloads = {"traversal", "lookup", "aggregation", "mixed"}
    if args.skip_mixed:
        selected_workloads.discard("mixed")

    prepared_dir = PROJECT_ROOT / cfg["dataset"]["prepared_dir"]
    raw_dir = PROJECT_ROOT / cfg.get("raw_directory", "results/raw")
    processed_dir = PROJECT_ROOT / cfg.get("processed_directory", "results/processed")
    start_nodes = ensure_start_nodes(cfg, prepared_dir)

    status = credential_status()
    skip_missing = args.skip_missing or args.database.lower().strip() == "all"
    runnable: list[str] = []
    for name in targets:
        if status[name]["ready"]:
            runnable.append(name)
        else:
            missing = ", ".join(status[name]["missing"])  # type: ignore[arg-type]
            msg = f"{name}: NOT RUN / CREDENTIALS REQUIRED (missing: {missing})"
            if skip_missing:
                print(f"SKIP {msg}")
            else:
                print(f"FAILURE: {msg}")
                return 1

    if not runnable:
        print("FAILURE: No databases with credentials available to run.")
        return 1

    codes = [
        run_one_database(
            db_name=name,
            selected_workloads=selected_workloads,
            cfg=cfg,
            start_nodes=start_nodes,
            raw_dir=raw_dir,
            processed_dir=processed_dir,
            prepared_dir=prepared_dir,
        )
        for name in runnable
    ]
    hard_failures = sum(1 for code in codes if code == 1)
    soft_failures = sum(1 for code in codes if code == 2)
    print(
        f"\nAll requested runs finished. "
        f"okish={len(codes) - hard_failures} hard_failures={hard_failures} "
        f"with_query_errors={soft_failures}"
    )
    if hard_failures:
        return 1
    if soft_failures:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
