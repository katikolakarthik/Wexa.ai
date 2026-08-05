#!/usr/bin/env python3
"""Load the canonical prepared dataset into one or more databases.

Examples:
  python scripts/load_data.py --database cognodb --clear
  python scripts/load_data.py --database neo4j --clear
  python scripts/load_data.py --database all --clear

Destructive clears require --clear. Dataset download/preparation time is excluded.
"""

from __future__ import annotations

import argparse
import sys
import time
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
from src.utils.config import load_benchmark_config
from src.utils.dataset_io import load_nodes_csv, load_relationships_csv
from src.workloads.ingestion import elapsed_ms, write_ingestion_result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load prepared dataset into a graph DB.")
    parser.add_argument(
        "--database",
        required=True,
        help=f"Target database or 'all'. Supported: {', '.join(ALL_DATABASES)}",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Destructively clear existing graph data before loading.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Override config batch_size for batched inserts.",
    )
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="Skip constraint/index creation.",
    )
    parser.add_argument(
        "--skip-missing",
        action="store_true",
        help="When using --database all, skip DBs without credentials instead of failing.",
    )
    return parser.parse_args()


def load_one(
    *,
    name: str,
    nodes: list,
    relationships: list,
    batch_size: int,
    clear: bool,
    skip_schema: bool,
    raw_dir: Path,
) -> int:
    raw_result_path = raw_dir / f"{name}_ingestion.csv"
    result_row: dict = {
        "database": name,
        "batch_size": batch_size,
        "nodes_inserted": 0,
        "relationships_inserted": 0,
        "node_load_ms": "",
        "relationship_load_ms": "",
        "total_ingestion_ms": "",
        "nodes_per_second": "",
        "relationships_per_second": "",
        "verified_node_count": "",
        "verified_relationship_count": "",
        "counts_match": "",
        "success": False,
        "error": "",
    }

    adapter: GraphDatabaseAdapter = get_adapter(name)
    print(f"\n=== Loading into {name} ===")
    try:
        adapter.connect()
        existing = adapter.get_counts()  # type: ignore[attr-defined]
        print(
            f"Existing DB counts   : nodes={existing['nodes']:,} "
            f"relationships={existing['relationships']:,}"
        )

        if (existing["nodes"] or existing["relationships"]) and not clear:
            print(
                "FAILURE: Database is not empty. Re-run with --clear to allow "
                "destructive delete before reload."
            )
            result_row["error"] = "database_not_empty_clear_required"
            write_ingestion_result(raw_result_path, result_row)
            return 1

        if clear:
            print("Clearing database (--clear)...")
            clear_start = time.perf_counter_ns()
            adapter.clear_database()
            print(f"  Clear completed in {elapsed_ms(clear_start):.1f} ms")

        if not skip_schema:
            print("Creating schema...")
            try:
                adapter.create_schema()
                print("  Schema ready.")
            except Exception as exc:  # noqa: BLE001
                print(f"WARNING: schema creation failed: {exc}")
                print("  Continuing without full schema.")

        print("Loading nodes...")
        total_start = time.perf_counter_ns()
        node_metrics = adapter.load_nodes(nodes, batch_size)
        print(
            f"  Nodes inserted     : {node_metrics['inserted']:,} "
            f"in {node_metrics['duration_ms']:.1f} ms "
            f"({node_metrics['per_second']:.1f} nodes/s)"
        )

        print("Loading relationships...")
        rel_metrics = adapter.load_relationships(relationships, batch_size)
        total_ms = elapsed_ms(total_start)
        print(
            f"  Rels inserted      : {rel_metrics['inserted']:,} "
            f"in {rel_metrics['duration_ms']:.1f} ms "
            f"({rel_metrics['per_second']:.1f} rels/s)"
        )
        print(f"  Total ingestion    : {total_ms:.1f} ms")

        verified = adapter.get_counts()  # type: ignore[attr-defined]
        counts_match = (
            verified["nodes"] == len(nodes)
            and verified["relationships"] == len(relationships)
        )
        print(
            f"Verified DB counts   : nodes={verified['nodes']:,} "
            f"relationships={verified['relationships']:,}"
        )
        print(f"Counts match CSV     : {counts_match}")

        result_row.update(
            {
                "nodes_inserted": node_metrics["inserted"],
                "relationships_inserted": rel_metrics["inserted"],
                "node_load_ms": round(node_metrics["duration_ms"], 3),
                "relationship_load_ms": round(rel_metrics["duration_ms"], 3),
                "total_ingestion_ms": round(total_ms, 3),
                "nodes_per_second": round(node_metrics["per_second"], 3),
                "relationships_per_second": round(rel_metrics["per_second"], 3),
                "verified_node_count": verified["nodes"],
                "verified_relationship_count": verified["relationships"],
                "counts_match": counts_match,
                "success": counts_match,
                "error": "" if counts_match else "count_mismatch",
            }
        )
        write_ingestion_result(raw_result_path, result_row)
        if not counts_match:
            print("FAILURE: Loaded counts do not match prepared CSV counts.")
            return 1
        print(f"SUCCESS: {name} dataset loaded and verified.")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAILURE: {type(exc).__name__}: {exc}")
        result_row["error"] = f"{type(exc).__name__}: {exc}"
        write_ingestion_result(raw_result_path, result_row)
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

    batch_size = args.batch_size or int(cfg.get("batch_size", 1000))
    prepared_dir = PROJECT_ROOT / cfg["dataset"]["prepared_dir"]
    nodes_path = prepared_dir / cfg["dataset"]["nodes_file"]
    relationships_path = prepared_dir / cfg["dataset"]["relationships_file"]
    raw_dir = PROJECT_ROOT / cfg.get("raw_directory", "results/raw")

    if not nodes_path.is_file() or not relationships_path.is_file():
        print("FAILURE: Prepared dataset not found. Run prepare_dataset.py first.")
        return 1

    print("Loading prepared CSVs into memory (excluded from DB ingestion timer)...")
    nodes = load_nodes_csv(nodes_path)
    relationships = load_relationships_csv(relationships_path)
    print(f"  CSV nodes          : {len(nodes):,}")
    print(f"  CSV relationships  : {len(relationships):,}")
    print(f"  Batch size         : {batch_size}")

    status = credential_status()
    selected: list[str] = []
    for name in targets:
        if status[name]["ready"]:
            selected.append(name)
        else:
            missing = ", ".join(status[name]["missing"])  # type: ignore[arg-type]
            msg = f"{name}: NOT RUN / CREDENTIALS REQUIRED (missing: {missing})"
            if args.skip_missing or args.database.lower() == "all":
                print(f"SKIP {msg}")
            else:
                print(f"FAILURE: {msg}")
                return 1

    if not selected:
        print("FAILURE: No databases with credentials selected.")
        return 1

    codes = [
        load_one(
            name=name,
            nodes=nodes,
            relationships=relationships,
            batch_size=batch_size,
            clear=args.clear,
            skip_schema=args.skip_schema,
            raw_dir=raw_dir,
        )
        for name in selected
    ]
    failures = sum(1 for code in codes if code != 0)
    print(f"\nDone. successes={len(codes) - failures} failures={failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
