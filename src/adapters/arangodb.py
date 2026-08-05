"""ArangoDB adapter using AQL for logically equivalent workloads."""

from __future__ import annotations

import os
import time
from typing import Any, Iterable, Mapping

from arango import ArangoClient
from arango.database import StandardDatabase
from tqdm import tqdm

from src.adapters.base import GraphDatabaseAdapter
from src.utils.dataset_io import batched
from src.workloads.ingestion import elapsed_ms, throughput_per_second


class ArangoDBAdapter(GraphDatabaseAdapter):
    """ArangoDB implementation.

    Logical mapping:
    - Papers -> document collection ``papers`` with ``node_id`` / ``label``
    - CITES -> edge collection ``cites``
    - Named graph ``cit_hepph`` for traversals
    """

    name = "arangodb"
    NODE_COLLECTION = "papers"
    EDGE_COLLECTION = "cites"
    TEMP_COLLECTION = "benchmark_temp"
    GRAPH_NAME = "cit_hepph"

    def __init__(
        self,
        url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ) -> None:
        self.url = (url if url is not None else os.getenv("ARANGODB_URL", "")).strip()
        self.username = (
            username if username is not None else os.getenv("ARANGODB_USERNAME", "")
        ).strip()
        self.password = (
            password if password is not None else os.getenv("ARANGODB_PASSWORD", "")
        ).strip()
        self.database_name = (
            database if database is not None else os.getenv("ARANGODB_DATABASE", "_system")
        ).strip() or "_system"
        self._client: ArangoClient | None = None
        self._db: StandardDatabase | None = None

    def _require_credentials(self) -> None:
        missing = [
            name
            for name, value in (
                ("ARANGODB_URL", self.url),
                ("ARANGODB_USERNAME", self.username),
                ("ARANGODB_PASSWORD", self.password),
            )
            if not value or str(value).upper().startswith("YOUR_")
        ]
        if missing:
            raise ValueError(
                "Missing required ArangoDB environment variables: " + ", ".join(missing)
            )

    def connect(self) -> None:
        self._require_credentials()
        self._client = ArangoClient(hosts=self.url)
        self._db = self._client.db(
            self.database_name,
            username=self.username,
            password=self.password,
        )
        # Connectivity probe
        self._db.version()

    def close(self) -> None:
        self._db = None
        self._client = None

    def _ensure_connected(self) -> StandardDatabase:
        if self._db is None:
            raise RuntimeError("ArangoDB is not connected. Call connect() first.")
        return self._db

    def ping(self) -> bool:
        db = self._ensure_connected()
        cursor = db.aql.execute("RETURN 1")
        return list(cursor)[0] == 1

    def _paper_key(self, node_id: int | str) -> str:
        return f"n{int(node_id)}"

    def count_nodes(self) -> int:
        db = self._ensure_connected()
        if not db.has_collection(self.NODE_COLLECTION):
            return 0
        return int(db.collection(self.NODE_COLLECTION).count())

    def count_relationships(self) -> int:
        db = self._ensure_connected()
        if not db.has_collection(self.EDGE_COLLECTION):
            return 0
        return int(db.collection(self.EDGE_COLLECTION).count())

    def get_counts(self) -> dict[str, int]:
        return {"nodes": self.count_nodes(), "relationships": self.count_relationships()}

    def clear_database(self) -> None:
        db = self._ensure_connected()
        if db.has_graph(self.GRAPH_NAME):
            db.delete_graph(self.GRAPH_NAME, drop_collections=False)
        for name in (self.EDGE_COLLECTION, self.NODE_COLLECTION, self.TEMP_COLLECTION):
            if db.has_collection(name):
                db.delete_collection(name)

    def create_schema(self) -> None:
        db = self._ensure_connected()
        if not db.has_collection(self.NODE_COLLECTION):
            db.create_collection(self.NODE_COLLECTION)
        if not db.has_collection(self.EDGE_COLLECTION):
            db.create_collection(self.EDGE_COLLECTION, edge=True)
        if not db.has_collection(self.TEMP_COLLECTION):
            db.create_collection(self.TEMP_COLLECTION)
        if not db.has_graph(self.GRAPH_NAME):
            db.create_graph(
                self.GRAPH_NAME,
                edge_definitions=[
                    {
                        "edge_collection": self.EDGE_COLLECTION,
                        "from_vertex_collections": [self.NODE_COLLECTION],
                        "to_vertex_collections": [self.NODE_COLLECTION],
                    }
                ],
            )

        papers = db.collection(self.NODE_COLLECTION)
        # Persistent indexes for point + filtered lookup fairness.
        existing = {tuple(idx.get("fields", [])) for idx in papers.indexes()}
        if ("node_id",) not in existing:
            papers.add_persistent_index(fields=["node_id"], unique=True)
        if ("label",) not in existing:
            papers.add_persistent_index(fields=["label"], unique=False)

    def load_nodes(self, nodes: Iterable[Mapping[str, Any]], batch_size: int) -> dict[str, Any]:
        db = self._ensure_connected()
        self.create_schema()
        papers = db.collection(self.NODE_COLLECTION)
        node_list = list(nodes)
        start_ns = time.perf_counter_ns()
        inserted = 0
        for batch in tqdm(
            list(batched(node_list, batch_size)),
            desc="arangodb:node-batches",
            unit="batch",
        ):
            docs = [
                {
                    "_key": self._paper_key(row["node_id"]),
                    "node_id": int(row["node_id"]),
                    "label": row.get("label") or "Paper",
                }
                for row in batch
            ]
            papers.insert_many(docs, overwrite=False, silent=True)
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
        db = self._ensure_connected()
        self.create_schema()
        cites = db.collection(self.EDGE_COLLECTION)
        rel_list = list(relationships)
        start_ns = time.perf_counter_ns()
        inserted = 0
        for batch in tqdm(
            list(batched(rel_list, batch_size)),
            desc="arangodb:rel-batches",
            unit="batch",
        ):
            docs = []
            for row in batch:
                source = int(row["source"])
                target = int(row["target"])
                rel_type = row.get("relationship_type") or "CITES"
                docs.append(
                    {
                        "_from": f"{self.NODE_COLLECTION}/{self._paper_key(source)}",
                        "_to": f"{self.NODE_COLLECTION}/{self._paper_key(target)}",
                        "relationship_type": rel_type,
                        "source": source,
                        "target": target,
                    }
                )
            cites.insert_many(docs, silent=True)
            inserted += len(batch)
        end_ns = time.perf_counter_ns()
        duration_ms = elapsed_ms(start_ns, end_ns)
        return {
            "inserted": inserted,
            "batch_size": batch_size,
            "duration_ms": duration_ms,
            "duration_ns": end_ns - start_ns,
            "per_second": throughput_per_second(inserted, duration_ms),
            "relationship_types": sorted(
                {str(r.get("relationship_type") or "CITES") for r in rel_list}
            ),
        }

    def point_lookup(self, node_id: Any) -> Any:
        db = self._ensure_connected()
        cursor = db.aql.execute(
            """
            FOR p IN papers
              FILTER p.node_id == @node_id
              LIMIT 1
              RETURN {node_id: p.node_id, label: p.label}
            """,
            bind_vars={"node_id": int(node_id)},
        )
        rows = list(cursor)
        return rows[0] if rows else None

    def filtered_lookup(self, property_name: str, property_value: Any) -> Any:
        if property_name != "label":
            raise ValueError(
                "ArangoDB filtered_lookup in this suite indexes `label` only "
                f"(got {property_name!r})."
            )
        db = self._ensure_connected()
        cursor = db.aql.execute(
            """
            RETURN LENGTH(
              FOR p IN papers
                FILTER p.label == @value
                RETURN 1
            )
            """,
            bind_vars={"value": property_value},
        )
        return {"match_count": list(cursor)[0]}

    def one_hop(self, start_node_id: Any) -> Any:
        db = self._ensure_connected()
        start = f"{self.NODE_COLLECTION}/{self._paper_key(start_node_id)}"
        cursor = db.aql.execute(
            """
            FOR v IN 1..1 OUTBOUND @start GRAPH @graph
              RETURN DISTINCT v.node_id
            """,
            bind_vars={"start": start, "graph": self.GRAPH_NAME},
        )
        return {"neighbor_count": len(list(cursor))}

    def two_hop(self, start_node_id: Any) -> Any:
        db = self._ensure_connected()
        start = f"{self.NODE_COLLECTION}/{self._paper_key(start_node_id)}"
        cursor = db.aql.execute(
            """
            FOR v IN 2..2 OUTBOUND @start GRAPH @graph
              FILTER v.node_id != @node_id
              RETURN DISTINCT v.node_id
            """,
            bind_vars={
                "start": start,
                "graph": self.GRAPH_NAME,
                "node_id": int(start_node_id),
            },
        )
        return {"neighbor_count": len(list(cursor))}

    def three_hop(self, start_node_id: Any) -> Any:
        db = self._ensure_connected()
        start = f"{self.NODE_COLLECTION}/{self._paper_key(start_node_id)}"
        cursor = db.aql.execute(
            """
            FOR v IN 3..3 OUTBOUND @start GRAPH @graph
              FILTER v.node_id != @node_id
              RETURN DISTINCT v.node_id
            """,
            bind_vars={
                "start": start,
                "graph": self.GRAPH_NAME,
                "node_id": int(start_node_id),
            },
        )
        return {"neighbor_count": len(list(cursor))}

    def aggregation(self) -> Any:
        db = self._ensure_connected()
        cursor = db.aql.execute(
            """
            FOR e IN cites
              COLLECT relationship_type = e.relationship_type WITH COUNT INTO cnt
              SORT relationship_type
              RETURN {relationship_type, cnt}
            """
        )
        return list(cursor)

    def mixed_read(self, start_node_id: Any) -> Any:
        return self.one_hop(start_node_id)

    def mixed_write(self, payload: Mapping[str, Any]) -> Any:
        db = self._ensure_connected()
        if not db.has_collection(self.TEMP_COLLECTION):
            db.create_collection(self.TEMP_COLLECTION)
        temp_id = str(payload.get("temp_id"))
        doc = {
            "temp_id": temp_id,
            "worker_id": int(payload.get("worker_id", -1)),
        }
        db.collection(self.TEMP_COLLECTION).insert(doc, silent=True)
        return {"temp_id": temp_id}

    def cleanup_benchmark_temp(self) -> int:
        db = self._ensure_connected()
        if not db.has_collection(self.TEMP_COLLECTION):
            return 0
        count = int(db.collection(self.TEMP_COLLECTION).count())
        db.collection(self.TEMP_COLLECTION).truncate()
        return count

    def get_resource_info(self) -> dict[str, Any]:
        return {
            "database": self.name,
            "deployment": "arangodb_cloud_or_self_hosted",
            "region": "not observable",
            "vcpu": "not observable",
            "ram_mb": "not observable",
            "storage_gib": "not observable",
            "query_language": "AQL",
            "notes": (
                "Uses native AQL for equivalent logical operations (not Cypher). "
                "Document Oasis/self-hosted resources; do not claim CognoDB c0 parity "
                "unless verified."
            ),
        }
