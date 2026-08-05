# Benchmark result tables (generated)
Source: `results/processed/summary.csv` and `results/raw/*_ingestion.csv`.
Shared prepared graph: deterministic cit-HepPh subsample (399,000 relationships, seed 42) loaded on all five platforms to stay under Neo4j Aura free’s 400,000 relationship cap.

## Ingestion
| Database | Nodes/s | Rels/s | Node load (ms) | Rel load (ms) | Total (ms) | Verified |
|----------|--------:|-------:|---------------:|--------------:|-----------:|----------|
| arangodb | 1198.5 | 2205.7 | 28776.9 | 180896.8 | 212674.3 | 34489/399000 |
| cognodb | 1833.8 | 1949.5 | 18807.6 | 204663.6 | 223554.5 | 34489/399000 |
| falkordb | 12009.4 | 6728.0 | 2871.8 | 59304.2 | 62212.7 | 34489/399000 |
| memgraph | 3483.0 | 3502.3 | 9902.1 | 113925.4 | 123881.3 | 34489/399000 |
| neo4j | 10238.0 | 8047.8 | 3368.7 | 49578.7 | 53042.8 | 34489/399000 |

## Traversal
| Database | Workload | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) | QPS | errors |
|----------|----------|---------:|---------:|---------:|----------:|----:|-------:|
| cognodb | one_hop | 249.5 | 261.8 | 285.5 | 251.3 | 3.98 | 0 |
| memgraph | one_hop | 220.5 | 230.7 | 497.1 | 231.1 | 4.33 | 0 |
| falkordb | one_hop | 26.1 | 28.5 | 30.2 | 26.1 | 38.20 | 0 |
| arangodb | one_hop | 260.5 | 301.1 | 303.8 | 270.8 | 3.69 | 0 |
| neo4j | one_hop | 54.0 | 58.3 | 224.1 | 60.0 | 16.67 | 0 |
| cognodb | two_hop | 250.2 | 293.5 | 341.4 | 275.6 | 3.63 | 0 |
| memgraph | two_hop | 220.3 | 224.3 | 231.8 | 223.4 | 4.48 | 0 |
| falkordb | two_hop | 26.3 | 29.7 | 31.6 | 26.7 | 37.40 | 0 |
| arangodb | two_hop | 269.0 | 503.1 | 1052.5 | 324.7 | 3.08 | 0 |
| neo4j | two_hop | 54.4 | 58.1 | 145.8 | 57.3 | 17.44 | 0 |
| cognodb | three_hop | 255.7 | 1025.4 | 1815.1 | 397.1 | 2.52 | 0 |
| memgraph | three_hop | 221.3 | 231.4 | 859.0 | 244.2 | 4.09 | 0 |
| falkordb | three_hop | 26.0 | 28.6 | 29.9 | 26.2 | 38.12 | 0 |
| arangodb | three_hop | 300.9 | 3781.4 | 10218.9 | 1105.8 | 0.90 | 0 |
| neo4j | three_hop | 55.2 | 125.9 | 1014.0 | 110.0 | 9.08 | 0 |

## Lookup
| Database | Workload | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) | QPS | errors |
|----------|----------|---------:|---------:|---------:|----------:|----:|-------:|
| cognodb | point_lookup | 249.2 | 275.7 | 300.7 | 252.2 | 3.96 | 0 |
| memgraph | point_lookup | 220.3 | 224.5 | 236.4 | 220.9 | 4.53 | 0 |
| falkordb | point_lookup | 26.0 | 28.4 | 31.0 | 26.2 | 38.11 | 0 |
| arangodb | point_lookup | 259.5 | 304.5 | 722.3 | 276.4 | 3.62 | 0 |
| neo4j | point_lookup | 54.2 | 55.7 | 56.8 | 54.0 | 18.52 | 0 |
| cognodb | filtered_lookup | 339.3 | 413.1 | 505.8 | 338.0 | 2.96 | 0 |
| memgraph | filtered_lookup | 230.3 | 233.0 | 233.8 | 230.6 | 4.34 | 0 |
| falkordb | filtered_lookup | 28.8 | 30.5 | 31.8 | 28.9 | 34.61 | 0 |
| arangodb | filtered_lookup | 271.2 | 392.0 | 420.2 | 294.9 | 3.39 | 0 |
| neo4j | filtered_lookup | 57.4 | 59.4 | 59.8 | 57.5 | 17.38 | 0 |

## Aggregation
| Database | Workload | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) | QPS | errors |
|----------|----------|---------:|---------:|---------:|----------:|----:|-------:|
| cognodb | aggregation | 1504.0 | 2495.7 | 3328.9 | 1801.0 | 0.56 | 0 |
| memgraph | aggregation | 331.5 | 438.8 | 554.6 | 347.5 | 2.88 | 0 |
| falkordb | aggregation | 408.0 | 462.6 | 700.7 | 422.0 | 2.37 | 0 |
| arangodb | aggregation | 1890.1 | 2700.2 | 3409.8 | 1851.8 | 0.54 | 0 |
| neo4j | aggregation | 105.4 | 126.0 | 410.3 | 114.5 | 8.73 | 0 |

## Mixed
| Database | Workload | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) | QPS | errors |
|----------|----------|---------:|---------:|---------:|----------:|----:|-------:|
| cognodb | mixed_c1 | 250.1 | 1174.3 | 1571.5 | 472.0 | 2.12 | 0 |
| memgraph | mixed_c1 | 220.5 | 286.7 | 327.3 | 226.7 | 4.41 | 0 |
| falkordb | mixed_c1 | 26.1 | 29.7 | 31.4 | 26.4 | 37.77 | 0 |
| arangodb | mixed_c1 | 294.4 | 598.1 | 642.5 | 351.0 | 2.85 | 0 |
| neo4j | mixed_c1 | 55.3 | 93.2 | 372.1 | 65.2 | 15.33 | 0 |
| cognodb | mixed_c10 | 288.6 | 1395.4 | 2121.0 | 445.9 | 21.93 | 0 |
| memgraph | mixed_c10 | 225.0 | 239.8 | 1329.4 | 270.3 | 36.83 | 0 |
| falkordb | mixed_c10 | 25.5 | 255.4 | 507.4 | 51.8 | 192.26 | 0 |
| arangodb | mixed_c10 | 294.8 | 597.0 | 690.0 | 352.6 | 28.11 | 0 |
| neo4j | mixed_c10 | 56.3 | 120.4 | 1472.8 | 109.5 | 90.88 | 0 |
| cognodb | mixed_c40 | 289.5 | 1327.5 | 2575.8 | 480.4 | 81.26 | 0 |
| memgraph | mixed_c40 | 225.8 | 243.3 | 299.6 | 238.9 | 166.56 | 0 |
| falkordb | mixed_c40 | 25.3 | 29.7 | 39.9 | 53.3 | 591.39 | 0 |
| arangodb | mixed_c40 | 399.3 | 879.9 | 1207.1 | 469.6 | 83.73 | 0 |
| neo4j | mixed_c40 | 75.4 | 163.8 | 405.6 | 90.5 | 429.99 | 0 |
