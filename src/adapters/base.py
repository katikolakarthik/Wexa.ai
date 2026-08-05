"""Abstract adapter interface for graph database benchmarks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable, Mapping


class GraphDatabaseAdapter(ABC):
    """Logical operations shared by every database under test.

    Implementations must keep the *logical* workload identical even when
    query languages differ (Cypher vs AQL, etc.). Do not fake compatibility.
    """

    name: str = "base"

    @abstractmethod
    def connect(self) -> None:
        """Establish a connection using credentials from the environment."""

    @abstractmethod
    def close(self) -> None:
        """Close the driver/client and release resources."""

    @abstractmethod
    def clear_database(self) -> None:
        """Remove benchmark data. Must only be called with an explicit flag."""

    @abstractmethod
    def create_schema(self) -> None:
        """Create indexes / constraints required for fair lookup workloads."""

    @abstractmethod
    def load_nodes(self, nodes: Iterable[Mapping[str, Any]], batch_size: int) -> dict[str, Any]:
        """Load nodes in batches. Returns ingestion timing/metrics."""

    @abstractmethod
    def load_relationships(
        self, relationships: Iterable[Mapping[str, Any]], batch_size: int
    ) -> dict[str, Any]:
        """Load relationships in batches. Returns ingestion timing/metrics."""

    @abstractmethod
    def point_lookup(self, node_id: Any) -> Any:
        """Lookup a single node by canonical node_id."""

    @abstractmethod
    def filtered_lookup(self, property_name: str, property_value: Any) -> Any:
        """Lookup nodes by an indexed/filterable property."""

    @abstractmethod
    def one_hop(self, start_node_id: Any) -> Any:
        """Return nodes directly connected to start_node_id."""

    @abstractmethod
    def two_hop(self, start_node_id: Any) -> Any:
        """Return nodes two hops from start_node_id."""

    @abstractmethod
    def three_hop(self, start_node_id: Any) -> Any:
        """Return nodes three hops from start_node_id."""

    @abstractmethod
    def aggregation(self) -> Any:
        """Run the shared aggregation workload (e.g. count by rel type)."""

    @abstractmethod
    def mixed_read(self, start_node_id: Any) -> Any:
        """One mixed-workload read operation."""

    @abstractmethod
    def mixed_write(self, payload: Mapping[str, Any]) -> Any:
        """One mixed-workload write against temporary benchmark entities."""

    @abstractmethod
    def get_resource_info(self) -> dict[str, Any]:
        """Return observable resource metadata; use 'not observable' otherwise."""

    def ping(self) -> bool:
        """Optional connectivity probe. Override when a cheap health query exists."""
        raise NotImplementedError(f"{self.name} does not implement ping()")

    def __enter__(self) -> GraphDatabaseAdapter:
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
