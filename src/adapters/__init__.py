"""Database adapters for logically equivalent workloads across platforms."""

from src.adapters.arangodb import ArangoDBAdapter
from src.adapters.base import GraphDatabaseAdapter
from src.adapters.cognodb import CognoDBAdapter
from src.adapters.falkordb import FalkorDBAdapter
from src.adapters.memgraph import MemgraphAdapter
from src.adapters.neo4j_db import Neo4jAdapter
from src.adapters.registry import ALL_DATABASES, credential_status, get_adapter

__all__ = [
    "ALL_DATABASES",
    "ArangoDBAdapter",
    "CognoDBAdapter",
    "FalkorDBAdapter",
    "GraphDatabaseAdapter",
    "MemgraphAdapter",
    "Neo4jAdapter",
    "credential_status",
    "get_adapter",
]
