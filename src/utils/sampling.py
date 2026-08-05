"""Deterministic start-node selection shared across all database adapters."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Sequence


def select_start_nodes(
    node_ids: Sequence[int],
    *,
    count: int,
    seed: int,
) -> list[int]:
    """Return a fixed, sorted sample of start node IDs.

    Sampling order is determined solely by ``seed`` and the unique node ID set.
    The returned list is sorted for stable iteration across platforms/runs.
    """
    unique = sorted({int(n) for n in node_ids})
    if count <= 0:
        raise ValueError(f"count must be positive, got {count}")
    if count > len(unique):
        raise ValueError(
            f"Requested {count} start nodes but only {len(unique)} unique IDs available."
        )
    rng = random.Random(seed)
    chosen = rng.sample(unique, k=count)
    return sorted(chosen)


def save_start_nodes(path: Path, node_ids: Sequence[int], *, seed: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "random_seed": seed,
        "count": len(node_ids),
        "start_node_ids": [int(n) for n in node_ids],
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def load_start_nodes(path: Path) -> list[int]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [int(n) for n in payload["start_node_ids"]]
