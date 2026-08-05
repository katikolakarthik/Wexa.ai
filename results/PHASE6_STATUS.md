# Phase 6 / submission run status

Generated from live loads/benchmarks on the **shared Aura-safe subsample**. No fabricated numbers.

## Dataset (identical for all five databases)

| Field | Value |
|-------|------:|
| Name | cit-HepPh (SNAP) + deterministic subsample |
| Nodes | 34,489 |
| Relationships | 399,000 |
| Subsample seed | 42 |
| Full unique edges before subsample | 421,534 |
| Raw SHA-256 | `917e77b3344aed33fd2d849443c9512b7c528b9dc87251d4245fb3777bbe4128` |
| Prepared relationships SHA-256 | `0ca016b1b970f0249f121facde5c71b93d9fce45125fbe9122c9d85ab8e5b56d` |
| Start-node seed | 42 |

Preparation command:

```powershell
python scripts/prepare_dataset.py --aura-safe --seed 42
```

## Load status

| Database | Status | Verified counts |
|----------|--------|-----------------|
| cognodb | LOADED | 34,489 / 399,000 |
| neo4j | LOADED | 34,489 / 399,000 |
| memgraph | LOADED | 34,489 / 399,000 |
| falkordb | LOADED | 34,489 / 399,000 |
| arangodb | LOADED | 34,489 / 399,000 |

## Benchmark status

| Database | Workloads | Query errors |
|----------|-----------|--------------|
| cognodb | traversal, lookup, aggregation, mixed (1/10/40) | 0 |
| neo4j | traversal, lookup, aggregation, mixed (1/10/40) | 0 |
| memgraph | traversal, lookup, aggregation, mixed (1/10/40) | 0 |
| falkordb | traversal, lookup, aggregation, mixed (1/10/40) | 0 |
| arangodb | traversal, lookup, aggregation, mixed (1/10/40) | 0 |

## Artifacts

- `results/raw/*_latency.csv`
- `results/raw/*_mixed.csv`
- `results/raw/*_ingestion.csv`
- `results/processed/summary.csv`
- `results/processed/report_tables.md`
- `charts/*.png`

## Fairness caveats (mandatory)

1. Graph is an **Aura-safe seeded subsample** (399k edges), not the full 421,534-edge cit-HepPh unique set, so Neo4j Aura free can participate under an **identical** prepared CSV shared by all platforms.
2. Competitor deployments are **not** claimed to match CognoDB c0 (0.5 burst vCPU / 512 MB / 1 GiB / us-east4).
3. Observed latency differences may reflect region, tier, memory, and throttling — not only engine quality.
4. FalkorDB Cloud instance region from Browser was **ap-south-1**; CognoDB was **us-east4** — client RTT differs.
5. Results are real measurements in `results/`; do not invent rankings without these caveats.
