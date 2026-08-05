"""FalkorDB adapter (Cypher over Redis/FalkorDB Python client)."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Any, Iterable, Mapping

from falkordb import FalkorDB
from tqdm import tqdm

from src.adapters.base import GraphDatabaseAdapter
from src.utils.dataset_io import batched
from src.workloads.ingestion import elapsed_ms, throughput_per_second


class FalkorDBAdapter(GraphDatabaseAdapter):
    name = "falkordb"
    NODE_LABEL = "Paper"
    DEFAULT_REL_TYPE = "CITES"
    GRAPH_NAME_ENV = "FALKORDB_GRAPH"
    DEFAULT_GRAPH = "benchmark"

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        password: str | None = None,
        username: str | None = None,
        graph_name: str | None = None,
        ssl: bool | None = None,
    ) -> None:
        self.host = (host if host is not None else os.getenv("FALKORDB_HOST", "")).strip()
        # Allow accidental host:port in FALKORDB_HOST
        if self.host.count(":") == 1 and not self.host.startswith("["):
            maybe_host, maybe_port = self.host.rsplit(":", 1)
            if maybe_port.isdigit():
                self.host = maybe_host
                if port is None and not os.getenv("FALKORDB_PORT"):
                    port = int(maybe_port)
        port_raw = (
            str(port)
            if port is not None
            else os.getenv("FALKORDB_PORT", "6379")
        )
        self.port = int(port_raw)
        self.password = (
            password if password is not None else os.getenv("FALKORDB_PASSWORD", "")
        ).strip() or None
        self.username = (
            username if username is not None else os.getenv("FALKORDB_USERNAME", "")
        ).strip() or None
        self.graph_name = (
            graph_name
            if graph_name is not None
            else os.getenv(self.GRAPH_NAME_ENV, self.DEFAULT_GRAPH)
        ).strip()
        ssl_env = os.getenv("FALKORDB_SSL", "false").strip().lower()
        self.ssl = ssl if ssl is not None else ssl_env in {"1", "true", "yes"}
        self._client: FalkorDB | None = None
        self._graph = None

    def _require_credentials(self) -> None:
        if not self.host or self.host.upper().startswith("YOUR_"):
            raise ValueError("Missing required FalkorDB environment variable: FALKORDB_HOST")

    def connect(self) -> None:
        self._require_credentials()
        kwargs: dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "ssl": self.ssl,
            "socket_connect_timeout": float(os.getenv("FALKORDB_CONNECT_TIMEOUT", "15")),
            "socket_timeout": float(os.getenv("FALKORDB_SOCKET_TIMEOUT", "120")),
        }
        if self.password is not None:
            kwargs["password"] = self.password
        if self.username is not None:
            kwargs["username"] = self.username
        # Cloud endpoints often use certs that fail strict verification.
        if self.ssl:
            cert_reqs = os.getenv("FALKORDB_SSL_CERT_REQS", "none").strip().lower()
            kwargs["ssl_cert_reqs"] = None if cert_reqs in {"none", "null"} else cert_reqs
            kwargs["ssl_check_hostname"] = (
                os.getenv("FALKORDB_SSL_CHECK_HOSTNAME", "false").strip().lower()
                in {"1", "true", "yes"}
            )
        self._client = FalkorDB(**kwargs)
        self._graph = self._client.select_graph(self.graph_name)
        # Connectivity probe
        self._graph.query("RETURN 1 AS result")

    def close(self) -> None:
        self._graph = None
        self._client = None

    def _ensure_connected(self) -> None:
        if self._graph is None:
            raise RuntimeError("FalkorDB is not connected. Call connect() first.")

    def ping(self) -> bool:
        self._ensure_connected()
        result = self._graph.query("RETURN 1 AS result")
        rows = result.result_set or []
        return bool(rows and int(rows[0][0]) == 1)

    def _query(self, cypher: str, params: dict[str, Any] | None = None):
        self._ensure_connected()
        return self._graph.query(cypher, params or {})

    def count_nodes(self) -> int:
        rows = self._query("MATCH (n) RETURN count(n)").result_set or []
        return int(rows[0][0]) if rows else 0

    def count_relationships(self) -> int:
        rows = self._query("MATCH ()-[r]->() RETURN count(r)").result_set or []
        return int(rows[0][0]) if rows else 0

    def get_counts(self) -> dict[str, int]:
        return {"nodes": self.count_nodes(), "relationships": self.count_relationships()}

    def clear_database(self) -> None:
        # Dropping the named graph is the cleanest destructive reset for FalkorDB.
        self._ensure_connected()
        try:
            self._graph.delete()
        except Exception:
            # Fallback: detach-delete all nodes if delete() is unavailable/unauthorized.
            self._query("MATCH (n) DETACH DELETE n")
        self._graph = self._client.select_graph(self.graph_name)

    def create_schema(self) -> None:
        self._ensure_connected()
        # Prefer native FalkorDB index/constraint helpers when available.
        try:
            self._graph.create_node_unique_constraint(self.NODE_LABEL, "node_id")
        except Exception:
            pass
        try:
            self._graph.create_node_range_index(self.NODE_LABEL, "label")
        except Exception:
            pass

    def load_nodes(self, nodes: Iterable[Mapping[str, Any]], batch_size: int) -> dict[str, Any]:
        node_list = list(nodes)
        start_ns = time.perf_counter_ns()
        inserted = 0
        query = f"""
        UNWIND $rows AS row
        CREATE (p:{self.NODE_LABEL} {{node_id: row.node_id, label: row.label}})
        """
        for batch in tqdm(
            list(batched(node_list, batch_size)),
            desc="falkordb:node-batches",
            unit="batch",
        ):
            self._query(query, {"rows": batch})
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
        rel_list = list(relationships)
        start_ns = time.perf_counter_ns()
        inserted = 0
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rel in rel_list:
            rel_type = str(rel.get("relationship_type") or self.DEFAULT_REL_TYPE)
            by_type[rel_type].append(
                {"source": int(rel["source"]), "target": int(rel["target"])}
            )
        for rel_type, rows in by_type.items():
            self._assert_safe_rel_type(rel_type)
            query = f"""
            UNWIND $rows AS row
            MATCH (a:{self.NODE_LABEL} {{node_id: row.source}})
            MATCH (b:{self.NODE_LABEL} {{node_id: row.target}})
            CREATE (a)-[:{rel_type}]->(b)
            """
            for batch in tqdm(
                list(batched(rows, batch_size)),
                desc=f"falkordb:rel-batches[{rel_type}]",
                unit="batch",
            ):
                self._query(query, {"rows": batch})
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

    def _single_map(self, cypher: str, params: dict[str, Any], keys: list[str]) -> dict[str, Any] | None:
        rows = self._query(cypher, params).result_set or []
        if not rows:
            return None
        return {key: rows[0][idx] for idx, key in enumerate(keys)}

    def point_lookup(self, node_id: Any) -> Any:
        return self._single_map(
            f"""
            MATCH (p:{self.NODE_LABEL} {{node_id: $node_id}})
            RETURN p.node_id, p.label
            """,
            {"node_id": int(node_id)},
            ["node_id", "label"],
        )

    def filtered_lookup(self, property_name: str, property_value: Any) -> Any:
        self._assert_safe_property(property_name)
        return self._single_map(
            f"""
            MATCH (p:{self.NODE_LABEL})
            WHERE p.{property_name} = $value
            RETURN count(p)
            """,
            {"value": property_value},
            ["match_count"],
        )

    def one_hop(self, start_node_id: Any) -> Any:
        return self._single_map(
            f"""
            MATCH (a:{self.NODE_LABEL} {{node_id: $node_id}})-[:{self.DEFAULT_REL_TYPE}]->(b)
            RETURN count(DISTINCT b)
            """,
            {"node_id": int(start_node_id)},
            ["neighbor_count"],
        )

    def two_hop(self, start_node_id: Any) -> Any:
        return self._single_map(
            f"""
            MATCH (a:{self.NODE_LABEL} {{node_id: $node_id}})
                  -[:{self.DEFAULT_REL_TYPE}]->()-[:{self.DEFAULT_REL_TYPE}]->(b)
            WHERE b.node_id <> $node_id
            RETURN count(DISTINCT b)
            """,
            {"node_id": int(start_node_id)},
            ["neighbor_count"],
        )

    def three_hop(self, start_node_id: Any) -> Any:
        return self._single_map(
            f"""
            MATCH (a:{self.NODE_LABEL} {{node_id: $node_id}})
                  -[:{self.DEFAULT_REL_TYPE}]->()
                  -[:{self.DEFAULT_REL_TYPE}]->()
                  -[:{self.DEFAULT_REL_TYPE}]->(b)
            WHERE b.node_id <> $node_id
            RETURN count(DISTINCT b)
            """,
            {"node_id": int(start_node_id)},
            ["neighbor_count"],
        )

    def aggregation(self) -> Any:
        rows = self._query(
            """
            MATCH ()-[r]->()
            RETURN type(r), count(r)
            ORDER BY type(r)
            """
        ).result_set or []
        return [
            {"relationship_type": row[0], "cnt": row[1]}
            for row in rows
        ]

    def mixed_read(self, start_node_id: Any) -> Any:
        return self.one_hop(start_node_id)

    def mixed_write(self, payload: Mapping[str, Any]) -> Any:
        return self._single_map(
            """
            CREATE (n:BenchmarkTemp {
                temp_id: $temp_id,
                worker_id: $worker_id
            })
            RETURN n.temp_id
            """,
            {
                "temp_id": str(payload.get("temp_id")),
                "worker_id": int(payload.get("worker_id", -1)),
            },
            ["temp_id"],
        )

    def cleanup_benchmark_temp(self) -> int:
        before = self._query("MATCH (n:BenchmarkTemp) RETURN count(n)").result_set
        count = int(before[0][0]) if before else 0
        if count:
            self._query("MATCH (n:BenchmarkTemp) DETACH DELETE n")
        return count

    def get_resource_info(self) -> dict[str, Any]:
        return {
            "database": self.name,
            "deployment": "falkordb_cloud_or_self_hosted",
            "region": "not observable",
            "vcpu": "not observable",
            "ram_mb": "not observable",
            "storage_gib": "not observable",
            "graph_name": self.graph_name,
            "notes": (
                "Document FalkorDB Cloud plan or Docker host resources. "
                "Do not claim CognoDB c0 parity unless verified."
            ),
        }
