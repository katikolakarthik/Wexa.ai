"""Prepare canonical nodes.csv and relationships.csv from SNAP cit-HepPh.

Output schema
-------------
nodes.csv
  node_id,label

relationships.csv
  source,target,relationship_type

Preparation is deterministic. Duplicate edges in the source are collapsed.
Self-loops are removed. Optional seeded subsample supports Neo4j Aura free
(≤400k relationships) by producing one shared graph for all platforms.
"""

from __future__ import annotations

import csv
import gzip
import json
import random
from collections import OrderedDict
from dataclasses import asdict, dataclass
from pathlib import Path

from dataset.download import (
    DATASET_NAME,
    DATASET_PAGE,
    DOWNLOAD_URL,
    RAW_FILENAME,
    default_raw_dir,
    download_file,
    sha256_file,
)

RELATIONSHIP_TYPE = "CITES"
NODE_LABEL = "Paper"
MIN_RELATIONSHIPS = 100_000
TARGET_MAX_RELATIONSHIPS = 500_000
# Keep headroom under Neo4j Aura free's hard 400_000 relationship cap.
AURA_SAFE_MAX_RELATIONSHIPS = 399_000


@dataclass(frozen=True)
class PrepareResult:
    dataset_name: str
    source_page: str
    download_url: str
    raw_file: str
    raw_sha256: str
    raw_size_bytes: int
    node_count: int
    relationship_count: int
    self_loops_removed: int
    duplicate_edges_removed: int
    nodes_csv: str
    relationships_csv: str
    prepared_size_bytes: int
    preparation_notes: str
    full_relationship_count: int
    subsample_applied: bool
    subsample_seed: int | None
    max_relationships: int | None
    prepared_relationships_sha256: str


def default_prepared_dir(project_root: Path | None = None) -> Path:
    root = project_root or Path(__file__).resolve().parents[1]
    return root / "dataset" / "prepared"


def _parse_edge_line(line: str) -> tuple[int, int] | None:
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    parts = text.split()
    if len(parts) < 2:
        raise ValueError(f"Malformed edge line: {line!r}")
    return int(parts[0]), int(parts[1])


def read_edges_from_gz(raw_path: Path) -> tuple[list[tuple[int, int]], int, int]:
    """Return unique directed edges, counting dropped self-loops and duplicates."""
    edges: OrderedDict[tuple[int, int], None] = OrderedDict()
    self_loops = 0
    duplicates = 0

    with gzip.open(raw_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            parsed = _parse_edge_line(line)
            if parsed is None:
                continue
            source, target = parsed
            if source == target:
                self_loops += 1
                continue
            key = (source, target)
            if key in edges:
                duplicates += 1
                continue
            edges[key] = None

    return list(edges.keys()), self_loops, duplicates


def subsample_edges(
    edges: list[tuple[int, int]],
    *,
    max_relationships: int,
    seed: int,
) -> list[tuple[int, int]]:
    """Deterministically keep ``max_relationships`` edges (seeded sample).

    Selected edges are re-ordered by original parse index so CSVs stay stable
    for a given (seed, max_relationships) pair.
    """
    if max_relationships < 1:
        raise ValueError("max_relationships must be >= 1")
    if len(edges) <= max_relationships:
        return list(edges)

    rng = random.Random(seed)
    selected_indices = sorted(rng.sample(range(len(edges)), max_relationships))
    return [edges[i] for i in selected_indices]


def prepare_dataset(
    *,
    project_root: Path | None = None,
    force_download: bool = False,
    max_relationships: int | None = None,
    subsample_seed: int = 42,
) -> PrepareResult:
    """Download (if needed) and write canonical CSVs + manifest."""
    root = project_root or Path(__file__).resolve().parents[1]
    raw_dir = default_raw_dir(root)
    prepared_dir = default_prepared_dir(root)
    prepared_dir.mkdir(parents=True, exist_ok=True)

    raw_path = download_file(
        dest_path=raw_dir / RAW_FILENAME,
        force=force_download,
    )
    edges, self_loops, duplicates = read_edges_from_gz(raw_path)
    full_relationship_count = len(edges)

    subsample_applied = False
    applied_max: int | None = None
    applied_seed: int | None = None
    if max_relationships is not None and len(edges) > max_relationships:
        edges = subsample_edges(
            edges, max_relationships=max_relationships, seed=subsample_seed
        )
        subsample_applied = True
        applied_max = max_relationships
        applied_seed = subsample_seed

    if not (MIN_RELATIONSHIPS <= len(edges) <= TARGET_MAX_RELATIONSHIPS):
        raise ValueError(
            f"Prepared relationship count {len(edges)} is outside the target "
            f"band [{MIN_RELATIONSHIPS}, {TARGET_MAX_RELATIONSHIPS}]."
        )

    node_ids = sorted({node for edge in edges for node in edge})

    nodes_path = prepared_dir / "nodes.csv"
    relationships_path = prepared_dir / "relationships.csv"
    manifest_path = prepared_dir / "manifest.json"
    # Force start-node regeneration against the shared prepared node set.
    start_nodes_path = prepared_dir / "start_nodes.json"
    if start_nodes_path.exists():
        start_nodes_path.unlink()

    with nodes_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["node_id", "label"])
        writer.writeheader()
        for node_id in node_ids:
            writer.writerow({"node_id": node_id, "label": NODE_LABEL})

    with relationships_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["source", "target", "relationship_type"]
        )
        writer.writeheader()
        for source, target in edges:
            writer.writerow(
                {
                    "source": source,
                    "target": target,
                    "relationship_type": RELATIONSHIP_TYPE,
                }
            )

    prepared_size = nodes_path.stat().st_size + relationships_path.stat().st_size
    relationships_sha = sha256_file(relationships_path)

    if subsample_applied:
        notes = (
            "Deterministic parse of SNAP cit-HepPh.txt.gz. "
            "Comments skipped; self-loops removed; duplicate directed edges collapsed. "
            f"Then deterministic seeded subsample to {applied_max:,} relationships "
            f"(seed={applied_seed}) so Neo4j Aura free (400k rel cap) and all other "
            "platforms share one identical prepared graph. "
            f"Full unique edge count before subsample: {full_relationship_count:,}. "
            f"All relationships typed as {RELATIONSHIP_TYPE}; nodes labeled {NODE_LABEL}."
        )
    else:
        notes = (
            "Deterministic parse of SNAP cit-HepPh.txt.gz. "
            "Comments skipped; self-loops removed; duplicate directed edges collapsed. "
            "No relationship subsample applied. "
            f"All relationships typed as {RELATIONSHIP_TYPE}; nodes labeled {NODE_LABEL}."
        )

    result = PrepareResult(
        dataset_name=DATASET_NAME,
        source_page=DATASET_PAGE,
        download_url=DOWNLOAD_URL,
        raw_file=str(raw_path.relative_to(root)).replace("\\", "/"),
        raw_sha256=sha256_file(raw_path),
        raw_size_bytes=raw_path.stat().st_size,
        node_count=len(node_ids),
        relationship_count=len(edges),
        self_loops_removed=self_loops,
        duplicate_edges_removed=duplicates,
        nodes_csv=str(nodes_path.relative_to(root)).replace("\\", "/"),
        relationships_csv=str(relationships_path.relative_to(root)).replace(
            "\\", "/"
        ),
        prepared_size_bytes=prepared_size,
        preparation_notes=notes,
        full_relationship_count=full_relationship_count,
        subsample_applied=subsample_applied,
        subsample_seed=applied_seed,
        max_relationships=applied_max,
        prepared_relationships_sha256=relationships_sha,
    )

    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(result), handle, indent=2)
        handle.write("\n")

    return result


def main() -> int:
    result = prepare_dataset()
    print("Dataset preparation complete")
    print(f"  name              : {result.dataset_name}")
    print(f"  nodes             : {result.node_count:,}")
    print(f"  relationships     : {result.relationship_count:,}")
    print(f"  prepared size     : {result.prepared_size_bytes:,} bytes")
    print(f"  raw size          : {result.raw_size_bytes:,} bytes")
    print(f"  nodes.csv         : {result.nodes_csv}")
    print(f"  relationships.csv : {result.relationships_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
