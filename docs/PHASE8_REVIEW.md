# Phase 8 repository review

Review date: 2026-08-06 (updated after Aura-safe shared subsample re-run). Scope: fairness, reproducibility, security, code quality, documentation.

## Security

| Check | Status | Notes |
|-------|--------|-------|
| `.env` gitignored | PASS | Listed in `.gitignore` |
| `.env.example` placeholders only | PASS | No live secrets |
| Passwords never printed by scripts | PASS | Connection scripts print booleans / statuses only |
| Credentials absent from result CSVs | PASS | Latency/ingestion schemas have no auth fields |
| Secret scan of tracked docs/code | PASS | `scripts/scan_secrets.py` — only local `.env` (gitignored) plus placeholder/code parameter false positives |
| Credential rotation advice | DOCUMENTED | User pasted secrets in chat earlier; rotate vendor passwords |

Remaining operator action: keep rotating any credentials that appeared in chat history; never commit `.env`.

## Fairness

| Check | Status | Notes |
|-------|--------|-------|
| Same canonical dataset on all five | PASS | 34,489 / 399,000 verified on cognodb, neo4j, memgraph, falkordb, arangodb |
| Same start-node list / seed | PASS | seed `42`, `start_nodes.json` regenerated from shared node set |
| Logical adapters (Cypher vs AQL) | PASS | ArangoDB uses AQL equivalents |
| Resource parity claimed? | PASS (honest) | Explicitly **not** claimed |
| Neo4j Aura free included | PASS | Shared seed-42 subsample of 399,000 relationships (under 400k cap) |
| Region differences documented | PASS | CognoDB us-east4 vs FalkorDB ap-south-1 noted |

## Reproducibility

| Check | Status | Notes |
|-------|--------|-------|
| Pin `requirements.txt` | PASS | Versions pinned |
| Config defaults in `benchmark.yaml` | PASS | seed/warmup/iterations/concurrency |
| Dataset SHA recorded | PASS | raw + prepared relationships SHA in manifest / dataset README |
| Commands documented | PASS | README + `docs/COMPETITOR_SETUP.md`; `--aura-safe` prepare path |
| Charts regenerated from CSV | PASS | `scripts/generate_report.py` |
| Client environment capture | ADDED | `scripts/capture_environment.py` → `results/ENVIRONMENT.md` |
| Optional pipeline | ADDED | `scripts/run_pipeline.py` (no destroy without `--clear`) |

## Code quality

| Check | Status | Notes |
|-------|--------|-------|
| Unit tests (no cloud required) | PASS | `pytest` green |
| Adapter registry gating | PASS | Missing credentials → NOT RUN |
| Destructive clear gated | PASS | Requires explicit `--clear` |
| Ingestion CSV overwrite | FIXED | Latest successful load only (no mixed full/subsample rows) |

## Documentation deliverables

README Results/Charts/Analysis/Conclusions reflect the shared 399k subsample measurements. Competitor exact vCPU/RAM remain **not observable / unverified** except where Browser region for FalkorDB was noted.
