# Final submission validation matrix

Generated after shared Aura-safe subsample reload + full re-benchmark. No commit performed.

## Shared dataset reference

| Field | Value |
|-------|--------|
| Dataset | cit-HepPh (SNAP) → Aura-safe subsample |
| Nodes | 34,489 |
| Relationships | 399,000 |
| Subsample seed | 42 |
| Raw SHA-256 | `917e77b3344aed33fd2d849443c9512b7c528b9dc87251d4245fb3777bbe4128` |
| Prepared relationships SHA-256 | `0ca016b1b970f0249f121facde5c71b93d9fce45125fbe9122c9d85ab8e5b56d` |

## Per-database dataset + workload completion

| Database | Nodes | Rels | Dataset ref | Ingestion | Traversal | Lookup | Aggregation | Mixed |
|----------|------:|-----:|-------------|:---------:|:---------:|:------:|:-----------:|:-----:|
| cognodb | 34489 | 399000 | same prepared SHA above | yes | yes | yes | yes | yes |
| neo4j | 34489 | 399000 | same prepared SHA above | yes | yes | yes | yes | yes |
| memgraph | 34489 | 399000 | same prepared SHA above | yes | yes | yes | yes | yes |
| falkordb | 34489 | 399000 | same prepared SHA above | yes | yes | yes | yes | yes |
| arangodb | 34489 | 399000 | same prepared SHA above | yes | yes | yes | yes | yes |

## Measured metrics completeness

| Metric | cognodb | neo4j | memgraph | falkordb | arangodb |
|--------|:-------:|:-----:|:--------:|:--------:|:--------:|
| Ingestion throughput (rels/s) | yes | yes | yes | yes | yes |
| 1-hop p50/p95 | yes | yes | yes | yes | yes |
| 2-hop p50/p95 | yes | yes | yes | yes | yes |
| 3-hop p50/p95 | yes | yes | yes | yes | yes |
| Point lookup p50/p95 | yes | yes | yes | yes | yes |
| Indexed/filtered lookup p50/p95 | yes | yes | yes | yes | yes |
| Aggregation p50/p95 | yes | yes | yes | yes | yes |
| Mixed R/W throughput (c=1/10/40) | yes | yes | yes | yes | yes |
| Resource footprint (observable) | client + CognoDB UI | client only | client only | client + region | client only |

## Notes

- Query errors for all workloads on all five DBs: **0**
- `filtered_lookup` is the indexed/schema-backed filtered lookup workload
- Competitor exact vCPU/RAM/storage remain **not observable / unverified** in README
