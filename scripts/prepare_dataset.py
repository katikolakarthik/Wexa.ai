#!/usr/bin/env python3
"""Prepare the canonical public benchmark dataset (Phase 2 / Aura-safe subsample)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dataset.prepare import AURA_SAFE_MAX_RELATIONSHIPS, prepare_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare cit-HepPh nodes/relationships CSVs for all platforms."
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download the SNAP raw archive even if present.",
    )
    parser.add_argument(
        "--max-relationships",
        type=int,
        default=None,
        help=(
            "If full unique edge count exceeds this value, apply a deterministic "
            "seeded subsample so all platforms share one Aura-safe graph."
        ),
    )
    parser.add_argument(
        "--aura-safe",
        action="store_true",
        help=f"Alias for --max-relationships {AURA_SAFE_MAX_RELATIONSHIPS}.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed used only when a relationship subsample is applied.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    max_relationships = args.max_relationships
    if args.aura_safe:
        max_relationships = AURA_SAFE_MAX_RELATIONSHIPS

    result = prepare_dataset(
        project_root=PROJECT_ROOT,
        force_download=args.force_download,
        max_relationships=max_relationships,
        subsample_seed=args.seed,
    )

    print("Dataset preparation complete")
    print("----------------------------")
    print(f"Dataset name        : {result.dataset_name}")
    print(f"Source page         : {result.source_page}")
    print(f"Download URL        : {result.download_url}")
    print(f"Raw file            : {result.raw_file}")
    print(f"Raw SHA-256         : {result.raw_sha256}")
    print(f"Raw size (bytes)    : {result.raw_size_bytes:,}")
    print(f"Full unique edges   : {result.full_relationship_count:,}")
    print(f"Subsample applied   : {result.subsample_applied}")
    if result.subsample_applied:
        print(f"Subsample seed      : {result.subsample_seed}")
        print(f"Max relationships   : {result.max_relationships:,}")
    print(f"Node count          : {result.node_count:,}")
    print(f"Relationship count  : {result.relationship_count:,}")
    print(f"Self-loops removed  : {result.self_loops_removed:,}")
    print(f"Duplicate edges out : {result.duplicate_edges_removed:,}")
    print(f"Prepared size       : {result.prepared_size_bytes:,} bytes")
    print(f"Relationships SHA   : {result.prepared_relationships_sha256}")
    print(f"nodes.csv           : {result.nodes_csv}")
    print(f"relationships.csv   : {result.relationships_csv}")
    print(f"Notes               : {result.preparation_notes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
