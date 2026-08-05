"""Shared Bolt + Cypher adapter used by Neo4j and Memgraph."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Any, Iterable, Mapping

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError
from tqdm import tqdm

from src.adapters.base import GraphDatabaseAdapter
from src.adapters.cognodb import describe_neo4j_error
from src.utils.dataset_io import batched
from src.workloads.ingestion import elapsed_ms, throughput_per_second


class BoltCypherAdapter(GraphDatabaseAdapter):
    """Neo4j-driver Cypher adapter with dialect-specific schema DDL."""

    NODE_LABEL = "Paper"
    DEFAULT_REL_TYPE = "CITES"
    CLEAR_BATCH_SIZE = 10_000
    dialect: str = "neo4j"  # neo4j | memgraph

    def __init__(
        self,
        *,
        uri_env: str,
        username_env: str,
        password_env: str,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.uri_env = uri_env
        self.username_env = username_env
        self.password_env = password_env
        self.uri = (uri if uri is not None else os.getenv(uri_env, "")).strip()
        self.username = (
            username if username is not None else os.getenv(username_env, "")
        ).strip()
        self.password = (
            password if password is not None else os.getenv(password_env, "")
        ).strip()
        self._driver = None

    def _require_credentials(self) -> None:
        missing = []
        if not self.uri:
            missing.append(self.uri_env)
        # Memgraph may allow empty auth; still require URI.
        if self.name != "memgraph":
            if not self.username:
                missing.append(self.username_env)
            if not self.password:
                missing.append(self.password_env)
        if missing:
            raise ValueError(
                f"Missing required {self.name} environment variables: "
                + ", ".join(missing)
            )

    def connect(self) -> None:
        self._require_credentials()
        auth = None
        if self.username or self.password:
            auth = (self.username, self.password)
        self._driver = GraphDatabase.driver(
            self.uri,
            auth=auth,
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
            raise RuntimeError(f"{self.name} driver is not connected. Call connect() first.")

    def ping(self) -> bool:
        self._ensure_connected()
        assert self._driver is not None
        with self._driver.session() as session:
            record = session.run("RETURN 1 AS result").single()
            return bool(record and int(record["result"]) == 1)

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
        return {"nodes": self.count_nodes(), "relationships": self.count_relationships()}

    def clear_database(self) -> None:
        self._ensure_connected()
        assert self._driver is not None
        while True:
            with self._driver.session() as session:
                record = session.run(
                    """
                    MATCH (n)
                    WITH n LIMIT $limit
                    DETACH DELETE n
                    RETURN count(*) AS deleted
                    """,
                    limit=self.CLEAR_BATCH_SIZE,
                ).single()
                deleted = int(record["deleted"]) if record else 0
            if deleted == 0:
                break

    def create_schema(self) -> None:
        self._ensure_connected()
        assert self._driver is not None
        statements = self._schema_statements()
        errors: list[str] = []
        with self._driver.session() as session:
            for statement in statements:
                try:
                    session.run(statement).consume()
                except Neo4jError as exc:
                    errors.append(describe_neo4j_error(exc))
        if len(errors) == len(statements):
            raise RuntimeError(
                f"Unable to create schema on {self.name}: " + "; ".join(errors)
            )

    def _schema_statements(self) -> list[str]:
        if self.dialect == "memgraph":
            return [
                f"CREATE INDEX ON :{self.NODE_LABEL}(node_id);",
                f"CREATE INDEX ON :{self.NODE_LABEL}(label);",
                f"CREATE CONSTRAINT ON (p:{self.NODE_LABEL}) ASSERT p.node_id IS UNIQUE;",
            ]
        return [
            (
                "CREATE CONSTRAINT paper_node_id IF NOT EXISTS "
                f"FOR (p:{self.NODE_LABEL}) REQUIRE p.node_id IS UNIQUE"
            ),
            (
                "CREATE INDEX paper_node_id_idx IF NOT EXISTS "
                f"FOR (p:{self.NODE_LABEL}) ON (p.node_id)"
            ),
            (
                "CREATE INDEX paper_label IF NOT EXISTS "
                f"FOR (p:{self.NODE_LABEL}) ON (p.label)"
            ),
        ]

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
            for batch in tqdm(batches, desc=f"{self.name}:node-batches", unit="batch"):
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
                    batches, desc=f"{self.name}:rel-batches[{rel_type}]", unit="batch"
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
            raise ValueError(f"Unsupported relationship_type: {rel_type!r}")

    @staticmethod
    def _assert_safe_property(property_name: str) -> None:
        if not property_name.isidentifier():
            raise ValueError(f"Unsupported property name: {property_name!r}")

    def _run_single(self, query: str, **params: Any) -> Any:
        self._ensure_connected()
        assert self._driver is not None
        with self._driver.session() as session:
            record = session.run(query, **params).single()
            return dict(record) if record is not None else None

    def point_lookup(self, node_id: Any) -> Any:
        return self._run_single(
            f"""
            MATCH (p:{self.NODE_LABEL} {{node_id: $node_id}})
            RETURN p.node_id AS node_id, p.label AS label
            """,
            node_id=int(node_id),
        )

    def filtered_lookup(self, property_name: str, property_value: Any) -> Any:
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
        return self._run_single(
            f"""
            MATCH (a:{self.NODE_LABEL} {{node_id: $node_id}})-[:{self.DEFAULT_REL_TYPE}]->(b)
            RETURN count(DISTINCT b) AS neighbor_count
            """,
            node_id=int(start_node_id),
        )

    def two_hop(self, start_node_id: Any) -> Any:
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
        return self.one_hop(start_node_id)

    def mixed_write(self, payload: Mapping[str, Any]) -> Any:
        return self._run_single(
            """
            CREATE (n:BenchmarkTemp {
                temp_id: $temp_id,
                worker_id: $worker_id,
                created_at: timestamp()
            })
            RETURN n.temp_id AS temp_id
            """,
            temp_id=str(payload.get("temp_id")),
            worker_id=int(payload.get("worker_id", -1)),
        )

    def cleanup_benchmark_temp(self) -> int:
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
        return {
            "database": self.name,
            "deployment": "not observable",
            "region": "not observable",
            "vcpu": "not observable",
            "ram_mb": "not observable",
            "storage_gib": "not observable",
            "connections": "not observable",
            "status": "configured_via_env",
            "notes": "Fill platform resource details in README Resource Fairness after provisioning.",
        }
