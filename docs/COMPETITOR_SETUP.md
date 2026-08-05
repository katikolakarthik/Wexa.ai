# Competitor database setup (Phase 5)

Fill credentials in `.env` (never commit secrets). Then:

```powershell
python scripts/test_connections.py
python scripts/load_data.py --database neo4j --clear
python scripts/run_benchmark.py --database neo4j
```

Or run every ready database:

```powershell
python scripts/load_data.py --database all --clear
python scripts/run_benchmark.py --database all
```

## Neo4j

| Env | Example |
|-----|---------|
| `NEO4J_URI` | `neo4j+s://xxxx.databases.neo4j.io` (Aura) or `bolt://localhost:7687` |
| `NEO4J_USERNAME` | `neo4j` |
| `NEO4J_PASSWORD` | instance password |

Query language: Cypher (official `neo4j` driver).  
Indexed properties: `Paper.node_id` unique constraint, `Paper.label` index.

## Memgraph

| Env | Example |
|-----|---------|
| `MEMGRAPH_URI` | Cloud: `bolt+ssc://HOST:7687` (TLS + self-signed cert). Strict CA: `bolt+s://`. Local: `bolt://localhost:7687` |
| `MEMGRAPH_USERNAME` | Cloud project username (often your email). Optional locally. |
| `MEMGRAPH_PASSWORD` | Cloud project password. Optional locally. |

Query language: Cypher (Neo4j Python driver).  
Schema dialect uses Memgraph `CREATE INDEX ON :Label(prop)` / constraint syntax.

Memgraph Cloud matches the official Python snippet’s `encrypted=True` by using **TLS**. Cloud endpoints often use a **self-signed** certificate, so this suite defaults to / documents **`bolt+ssc://HOST:7687`** with the Neo4j driver. Plain `bolt://` against cloud fails the Bolt handshake.

Local Docker quickstart (document your host resources honestly):

```powershell
docker run -p 7687:7687 memgraph/memgraph-mage
```

## FalkorDB

| Env | Example |
|-----|---------|
| `FALKORDB_HOST` | Cloud host from FalkorDB Browser (no `:port` suffix) |
| `FALKORDB_PORT` | Browser port (often `6xxxx`, not always `6379`) |
| `FALKORDB_USERNAME` | usually `falkordb` |
| `FALKORDB_PASSWORD` | instance password |
| `FALKORDB_GRAPH` | `benchmark` (dedicated; avoid overwriting demo graphs) |
| `FALKORDB_SSL` | Cloud free single instances often need `false`; try `true` only if required |

Query language: Cypher via FalkorDB Python client (`GRAPH.QUERY`).  
Indexes: `create_node_unique_constraint(Paper, node_id)` + range index on `label`.

Use the **exact** connection host/port shown in the FalkorDB Browser header (example shape: `r-….cloud` / `61971`). Do not put `:port` inside `FALKORDB_HOST`.

## ArangoDB

| Env | Example |
|-----|---------|
| `ARANGODB_URL` | `https://xxxx.arangodb.cloud:8529` or `http://localhost:8529` |
| `ARANGODB_USERNAME` | `root` / Oasis user |
| `ARANGODB_PASSWORD` | password |
| `ARANGODB_DATABASE` | `_system` or dedicated DB |

Query language: **AQL** (not Cypher) — logical workloads are equivalent:

| Logical op | AQL approach |
|------------|--------------|
| point lookup | `FILTER p.node_id == @id` |
| filtered lookup | `FILTER p.label == @value` |
| 1/2/3-hop | `FOR v IN k..k OUTBOUND ... GRAPH` |
| aggregation | `COLLECT relationship_type ... WITH COUNT` |

Collections: `papers`, edge `cites`, graph `cit_hepph`, temp `benchmark_temp`.

## Resource fairness caveat

CognoDB c0 free tier under test is approximately:

- 0.5 burst vCPU
- 512 MB RAM (UI-reported)
- 1 GiB storage
- region us-east4

Competitor free/cloud tiers are often **not** identical. Record each platform’s real vCPU/RAM/storage/region in the main README after provisioning. Never claim parity unless verified. If a free tier cannot be sized near CognoDB, keep the caveat prominent in results analysis.
