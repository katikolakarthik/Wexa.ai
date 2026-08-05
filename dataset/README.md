# Benchmark Dataset

## Source

| Field | Value |
|-------|--------|
| Original dataset name | **cit-HepPh** (Arxiv High Energy Physics — Phenomenology citation network) |
| Provider | [Stanford SNAP](https://snap.stanford.edu/data/) |
| Source page | https://snap.stanford.edu/data/cit-HepPh.html |
| Download URL | https://snap.stanford.edu/data/cit-HepPh.txt.gz |
| Graph type | Directed citation network |
| Why selected | Public, reproducible, ~421k unique directed relationships after prep; within 100k–500k target |

Citation (SNAP): Leskovec, Kleinberg, and Faloutsos; Gehrke, Ginsparg, and Kleinberg (see SNAP page for full citations).

## Canonical prepared outputs

After running preparation:

| File | Columns |
|------|---------|
| `dataset/prepared/nodes.csv` | `node_id`, `label` |
| `dataset/prepared/relationships.csv` | `source`, `target`, `relationship_type` |
| `dataset/prepared/manifest.json` | Counts, hashes, paths, subsample metadata |

- Every node is labeled `Paper`.
- Every relationship is typed `CITES` (paper `source` cites paper `target`).

## Preparation procedure (deterministic)

1. Download `cit-HepPh.txt.gz` into `dataset/raw/` (skipped if already present).
2. Parse SNAP edge list lines (`source target`), ignoring comment lines starting with `#`.
3. Drop self-loops.
4. Collapse duplicate directed edges (first occurrence kept; insertion order preserved).
5. **Aura-safe subsample (current submission graph):** if unique edges exceed 399,000, keep a deterministic `random.Random(42).sample` of 399,000 edges (then restore original relative order). This stays under Neo4j Aura free’s hard **400,000** relationship cap so **all five platforms** load the identical prepared CSVs.
6. Collect the sorted unique node ID set from remaining edges.
7. Write `nodes.csv` and `relationships.csv`.
8. Write `manifest.json` with counts, sizes, raw SHA-256, and prepared relationships SHA-256.
9. Delete any prior `start_nodes.json` so the benchmark runner regenerates start nodes from the shared node set (seed 42).

## Counts and checksums (current prepared graph)

Values from `manifest.json` after `python scripts/prepare_dataset.py --aura-safe --seed 42`:

| Metric | Value |
|--------|------:|
| Nodes | 34,489 |
| Relationships (prepared / shared) | 399,000 |
| Full unique edges before subsample | 421,534 |
| Self-loops removed | 44 |
| Duplicate edges removed | 0 |
| Subsample seed | 42 |
| Raw archive size | 1,664,504 bytes |
| Raw SHA-256 | `917e77b3344aed33fd2d849443c9512b7c528b9dc87251d4245fb3777bbe4128` |
| Prepared relationships SHA-256 | see `manifest.json` → `prepared_relationships_sha256` |

SNAP’s published edge count is 421,578; after removing 44 self-loops the full unique directed edge count is **421,534**. The shared benchmark graph is the **399,000**-edge seeded subsample of that set.

## Commands

```powershell
# Shared Aura-safe graph used for all five databases:
python scripts/prepare_dataset.py --aura-safe --seed 42

# Full graph only (NOT Aura-compatible; do not mix with Neo4j free):
python scripts/prepare_dataset.py

# optional re-download:
python scripts/prepare_dataset.py --aura-safe --force-download
```

Raw downloads and prepared CSVs are gitignored; regenerate with the commands above. `manifest.json` and `start_nodes.json` are kept for reproducibility.
