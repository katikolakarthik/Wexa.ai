"""CognoDB Cloud adapter (Neo4j-compatible Bolt / Cypher)."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Any, Iterable, Mapping

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError
from tqdm import tqdm

from src.adapters.base import GraphDatabaseAdapter
from src.utils.dataset_io import batched
from src.workloads.ingestion import elapsed_ms, throughput_per_second


class CognoDBAdapter(GraphDatabaseAdapter):
    """Adapter for CognoDB Cloud using the official Neo4j Python driver.

    CognoDB speaks Bolt and understands Cypher. Credentials must come from:

    - COGNODB_URI
    - COGNODB_USERNAME
    - COGNODB_PASSWORD
    """

    name = "cognodb"
    NODE_LABEL = "Paper"
    DEFAULT_REL_TYPE = "CITES"
    CLEAR_BATCH_SIZE = 10_000

    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.uri = uri or os.getenv("COGNODB_URI", "").strip()
        self.username = username or os.getenv("COGNODB_USERNAME", "").strip()
        self.password = password or os.getenv("COGNODB_PASSWORD", "").strip()
        self._driver = None

    def _require_credentials(self) -> None:
        missing = [
            name
            for name, value in (
                ("COGNODB_URI", self.uri),
                ("COGNODB_USERNAME", self.username),
                ("COGNODB_PASSWORD", self.password),
            )
            if not value
        ]
        if missing:
            raise ValueError(
                "Missing required CognoDB environment variables: "
                + ", ".join(missing)
                + ". Copy .env.example to .env and fill in values from the CognoDB console."
            )

    def connect(self) -> None:
        self._require_credentials()
        # Never log password. URI may contain host info only.
        self._driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password),
            connection_timeout=60.0,
            max_connection_lifetime=3600,
        )
        self._driver.verify_connectivity()

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def _ensure_connected(self) -> None:
        if self._driver is None:
            raise RuntimeError("CognoDB driver is not connected. Call connect() first.")

    def ping(self) -> bool:
        """Execute RETURN 1 AS result and return True on success."""
        self._ensure_connected()
        assert self._driver is not None
        with self._driver.session() as session:
            record = session.run("RETURN 1 AS result").single()
            if record is None:
                return False
            return int(record["result"]) == 1

    def count_nodes(self) -> int:
        self._ensure_connected()
        assert self._driver is not None
        with self._driver.session() as session:
            record = session.run("MATCH (n) RETURN count(n) AS c").single()
            return int(record["c"]) if record else 0

    def count_relationships(self) -> int:
        self._ensure_connected()
        assert self._driver is not None
        with self._driver.session() as session:
            record = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()
            return int(record["c"]) if record else 0

    def get_counts(self) -> dict[str, int]:
        return {
            "nodes": self.count_nodes(),
            "relationships": self.count_relationships(),
        }

    def clear_database(self) -> None:
        """Detach-delete all nodes in batches. Destructive — call only with --clear."""
        self._ensure_connected()
        assert self._driver is not None
        while True:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (n)
                    WITH n LIMIT $limit
                    DETACH DELETE n
                    RETURN count(*) AS deleted
                    """,
                    limit=self.CLEAR_BATCH_SIZE,
                )
                record = result.single()
                deleted = int(record["deleted"]) if record else 0
            if deleted == 0:
                break

    def create_schema(self) -> None:
        """Create uniqueness/index on Paper.node_id and index on Paper.label."""
        self._ensure_connected()
        assert self._driver is not None
        statements = [
            (
                "CREATE CONSTRAINT paper_node_id IF NOT EXISTS "
                f"FOR (p:{self.NODE_LABEL}) REQUIRE p.node_id IS UNIQUE"
            ),
            (
                "CREATE INDEX paper_node_id IF NOT EXISTS "
                f"FOR (p:{self.NODE_LABEL}) ON (p.node_id)"
            ),
            (
                "CREATE INDEX paper_label IF NOT EXISTS "
                f"FOR (p:{self.NODE_LABEL}) ON (p.label)"
            ),
        ]
        errors: list[str] = []
        with self._driver.session() as session:
            for statement in statements:
                try:
                    session.run(statement).consume()
                except Neo4jError as exc:
                    errors.append(describe_neo4j_error(exc))
        # Require at least node_id access path.
        if len(errors) == len(statements):
            raise RuntimeError(
                "Unable to create any Paper schema objects on CognoDB: "
                + "; ".join(errors)
            )

    def load_nodes(self, nodes: Iterable[Mapping[str, Any]], batch_size: int) -> dict[str, Any]:
        self._ensure_connected()
        assert self._driver is not None
        node_list = list(nodes)
        start_ns = time.perf_counter_ns()
        inserted = 0

        query = f"""
        UNWIND $rows AS row
        CREATE (p:{self.NODE_LABEL} {{node_id: row.node_id, label: row.label}})
        """

        with self._driver.session() as session:
            batches = list(batched(node_list, batch_size))
            for batch in tqdm(batches, desc="cognodb:node-batches", unit="batch"):
                session.run(query, rows=batch).consume()
                inserted += len(batch)

        end_ns = time.perf_counter_ns()
        duration_ms = elapsed_ms(start_ns, end_ns)
        return {
            "inserted": inserted,
            "batch_size": batch_size,
            "duration_ms": duration_ms,
            "duration_ns": end_ns - start_ns,
            "per_second": throughput_per_second(inserted, duration_ms),
        }

    def load_relationships(
        self, relationships: Iterable[Mapping[str, Any]], batch_size: int
    ) -> dict[str, Any]:
        self._ensure_connected()
        assert self._driver is not None
        rel_list = list(relationships)
        start_ns = time.perf_counter_ns()
        inserted = 0

        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rel in rel_list:
            rel_type = str(rel.get("relationship_type") or self.DEFAULT_REL_TYPE)
            by_type[rel_type].append(
                {"source": int(rel["source"]), "target": int(rel["target"])}
            )

        with self._driver.session() as session:
            for rel_type, rows in by_type.items():
                self._assert_safe_rel_type(rel_type)
                query = f"""
                UNWIND $rows AS row
                MATCH (a:{self.NODE_LABEL} {{node_id: row.source}})
                MATCH (b:{self.NODE_LABEL} {{node_id: row.target}})
                CREATE (a)-[:{rel_type}]->(b)
                """
                batches = list(batched(rows, batch_size))
                for batch in tqdm(
                    batches,
                    desc=f"cognodb:rel-batches[{rel_type}]",
                    unit="batch",
                ):
                    session.run(query, rows=batch).consume()
                    inserted += len(batch)

        end_ns = time.perf_counter_ns()
        duration_ms = elapsed_ms(start_ns, end_ns)
        return {
            "inserted": inserted,
            "batch_size": batch_size,
            "duration_ms": duration_ms,
            "duration_ns": end_ns - start_ns,
            "per_second": throughput_per_second(inserted, duration_ms),
            "relationship_types": sorted(by_type.keys()),
        }

    @staticmethod
    def _assert_safe_rel_type(rel_type: str) -> None:
        if not rel_type.isidentifier() or not rel_type.isupper():
            # Prevent Cypher injection via relationship_type values.
            raise ValueError(
                f"Unsupported relationship_type for Cypher embedding: {rel_type!r}. "
                "Expected an uppercase identifier such as CITES."
            )

    @staticmethod
    def _assert_safe_property(property_name: str) -> None:
        if not property_name.isidentifier():
            raise ValueError(f"Unsupported property name: {property_name!r}")

    def _run_single(self, query: str, **params: Any) -> Any:
        self._ensure_connected()
        assert self._driver is not None
        with self._driver.session() as session:
            result = session.run(query, **params)
            record = result.single()
            return dict(record) if record is not None else None

    def point_lookup(self, node_id: Any) -> Any:
        """Lookup a Paper by unique node_id."""
        return self._run_single(
            f"""
            MATCH (p:{self.NODE_LABEL} {{node_id: $node_id}})
            RETURN p.node_id AS node_id, p.label AS label
            """,
            node_id=int(node_id),
        )

    def filtered_lookup(self, property_name: str, property_value: Any) -> Any:
        """Filtered lookup by indexed property; returns matching node_ids (capped)."""
        self._assert_safe_property(property_name)
        return self._run_single(
            f"""
            MATCH (p:{self.NODE_LABEL})
            WHERE p.{property_name} = $value
            RETURN count(p) AS match_count
            """,
            value=property_value,
        )

    def one_hop(self, start_node_id: Any) -> Any:
        """Count distinct nodes directly reachable via outgoing CITES."""
        return self._run_single(
            f"""
            MATCH (a:{self.NODE_LABEL} {{node_id: $node_id}})-[:{self.DEFAULT_REL_TYPE}]->(b)
            RETURN count(DISTINCT b) AS neighbor_count
            """,
            node_id=int(start_node_id),
        )

    def two_hop(self, start_node_id: Any) -> Any:
        """Count distinct nodes at exactly 2 outgoing hops via CITES."""
        return self._run_single(
            f"""
            MATCH (a:{self.NODE_LABEL} {{node_id: $node_id}})
                  -[:{self.DEFAULT_REL_TYPE}]->()-[:{self.DEFAULT_REL_TYPE}]->(b)
            WHERE b.node_id <> $node_id
            RETURN count(DISTINCT b) AS neighbor_count
            """,
            node_id=int(start_node_id),
        )

    def three_hop(self, start_node_id: Any) -> Any:
        """Count distinct nodes at exactly 3 outgoing hops via CITES."""
        return self._run_single(
            f"""
            MATCH (a:{self.NODE_LABEL} {{node_id: $node_id}})
                  -[:{self.DEFAULT_REL_TYPE}]->()
                  -[:{self.DEFAULT_REL_TYPE}]->()
                  -[:{self.DEFAULT_REL_TYPE}]->(b)
            WHERE b.node_id <> $node_id
            RETURN count(DISTINCT b) AS neighbor_count
            """,
            node_id=int(start_node_id),
        )

    def aggregation(self) -> Any:
        """Count relationships grouped by relationship type."""
        self._ensure_connected()
        assert self._driver is not None
        with self._driver.session() as session:
            records = session.run(
                """
                MATCH ()-[r]->()
                RETURN type(r) AS relationship_type, count(r) AS cnt
                ORDER BY relationship_type
                """
            )
            return [dict(record) for record in records]

    def mixed_read(self, start_node_id: Any) -> Any:
        """Mixed-workload read: 1-hop neighbor count from a fixed start node."""
        return self.one_hop(start_node_id)

    def mixed_write(self, payload: Mapping[str, Any]) -> Any:
        """Create a temporary BenchmarkTemp node (does not touch canonical Papers)."""
        temp_id = str(payload.get("temp_id"))
        worker_id = int(payload.get("worker_id", -1))
        return self._run_single(
            """
            CREATE (n:BenchmarkTemp {
                temp_id: $temp_id,
                worker_id: $worker_id,
                created_at: timestamp()
            })
            RETURN n.temp_id AS temp_id
            """,
            temp_id=temp_id,
            worker_id=worker_id,
        )

    def cleanup_benchmark_temp(self) -> int:
        """Delete temporary mixed-workload nodes. Returns deleted count."""
        self._ensure_connected()
        assert self._driver is not None
        deleted = 0
        while True:
            with self._driver.session() as session:
                record = session.run(
                    """
                    MATCH (n:BenchmarkTemp)
                    WITH n LIMIT $limit
                    DETACH DELETE n
                    RETURN count(*) AS deleted
                    """,
                    limit=self.CLEAR_BATCH_SIZE,
                ).single()
                batch = int(record["deleted"]) if record else 0
            deleted += batch
            if batch == 0:
                break
        return deleted

    def get_resource_info(self) -> dict[str, Any]:
        """Return documented CognoDB free-tier resources.

        Cloud-side usage counters are not queried by this adapter unless the
        platform later exposes an observable API. Values reflect config/UI.
        """
        return {
            "database": self.name,
            "deployment": "cloud_free_c0",
            "region": "us-east4",
            "vcpu": "0.5 burst (UI-reported)",
            "ram_mb": 512,
            "storage_gib": 1,
            "connections": 200,
            "disk_iops": 500,
            "stored_database_size": "not observable",
            "platform_reported_usage": "not observable",
            "notes": (
                "Assignment docs historically mentioned 256 MB RAM; "
                "current CognoDB UI reports 512 MB. Using UI-reported values."
            ),
        }


def describe_neo4j_error(exc: Neo4jError) -> str:
    """Safe error description without credentials."""
    code = getattr(exc, "code", None) or "Neo4jError"
    message = getattr(exc, "message", None) or str(exc)
    return f"{code}: {message}"
