#!/usr/bin/env python3
"""Optional end-to-end pipeline (non-destructive by default).

Steps:
  1) connectivity check
  2) dataset prepare (idempotent)
  3) optional load (--load requires --clear for non-empty DBs)
  4) optional benchmark
  5) report/charts
  6) capture client environment

Never clears databases unless --clear is explicitly provided with --load.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_step(label: str, args: list[str]) -> int:
    print(f"\n=== {label} ===")
    print(">", " ".join(args))
    completed = subprocess.run(args, cwd=PROJECT_ROOT)
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark pipeline orchestrator.")
    parser.add_argument(
        "--database",
        default="all",
        help="Target DB list or 'all' (default: all ready databases).",
    )
    parser.add_argument(
        "--load",
        action="store_true",
        help="Run data loading step (requires --clear if DB not empty).",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Pass --clear to load_data.py (destructive).",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run workloads after prepare (and optional load).",
    )
    parser.add_argument(
        "--skip-prepare",
        action="store_true",
        help="Skip dataset preparation.",
    )
    parser.add_argument(
        "--skip-report",
        action="store_true",
        help="Skip chart/table generation.",
    )
    args = parser.parse_args()

    if args.clear and not args.load:
        print("FAILURE: --clear requires --load (refusing bare destructive flag).")
        return 1

    steps: list[tuple[str, list[str]]] = [
        ("connectivity", [PYTHON, "scripts/test_connections.py"]),
    ]
    if not args.skip_prepare:
        steps.append(
            (
                "prepare_dataset",
                [PYTHON, "scripts/prepare_dataset.py", "--aura-safe", "--seed", "42"],
            )
        )

    if args.load:
        load_cmd = [
            PYTHON,
            "scripts/load_data.py",
            "--database",
            args.database,
        ]
        if args.clear:
            load_cmd.append("--clear")
        if args.database.lower() == "all":
            load_cmd.append("--skip-missing")
        steps.append(("load_data", load_cmd))

    if args.benchmark:
        bench_cmd = [
            PYTHON,
            "scripts/run_benchmark.py",
            "--database",
            args.database,
        ]
        if args.database.lower() == "all":
            bench_cmd.append("--skip-missing")
        steps.append(("run_benchmark", bench_cmd))

    if not args.skip_report:
        steps.append(("generate_report", [PYTHON, "scripts/generate_report.py"]))
        steps.append(
            ("capture_environment", [PYTHON, "scripts/capture_environment.py"])
        )

    failures = 0
    for label, cmd in steps:
        code = run_step(label, cmd)
        if code != 0:
            failures += 1
            print(f"Step '{label}' exited with code {code}")
            # Continue remaining non-dependent docs steps when possible.
            if label in {"load_data", "run_benchmark"}:
                print("Continuing remaining steps where possible...")
                continue
            if label == "connectivity":
                print("Continuing; some databases may be skipped later.")
                continue

    print(f"\nPipeline finished with {failures} failed step(s).")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
