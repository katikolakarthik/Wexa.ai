"""Shared dataset I/O helpers for benchmark loading."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterator


def iter_csv_dicts(path: Path) -> Iterator[dict[str, Any]]:
    """Yield CSV rows as dicts (streaming)."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        for row in reader:
            yield row


def load_nodes_csv(path: Path) -> list[dict[str, Any]]:
    """Load nodes.csv into memory with typed node_id."""
    nodes: list[dict[str, Any]] = []
    for row in iter_csv_dicts(path):
        nodes.append(
            {
                "node_id": int(row["node_id"]),
                "label": row.get("label") or "Paper",
            }
        )
    return nodes


def load_relationships_csv(path: Path) -> list[dict[str, Any]]:
    """Load relationships.csv into memory with typed endpoints."""
    relationships: list[dict[str, Any]] = []
    for row in iter_csv_dicts(path):
        relationships.append(
            {
                "source": int(row["source"]),
                "target": int(row["target"]),
                "relationship_type": row.get("relationship_type") or "CITES",
            }
        )
    return relationships


def batched(items: list[dict[str, Any]], batch_size: int) -> Iterator[list[dict[str, Any]]]:
    if batch_size <= 0:
        raise ValueError(f"batch_size must be positive, got {batch_size}")
    for index in range(0, len(items), batch_size):
        yield items[index : index + batch_size]
