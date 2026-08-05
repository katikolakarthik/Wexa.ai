"""Adapter factory / credential readiness helpers."""

from __future__ import annotations

import os
from typing import Callable

from src.adapters.arangodb import ArangoDBAdapter
from src.adapters.base import GraphDatabaseAdapter
from src.adapters.cognodb import CognoDBAdapter
from src.adapters.falkordb import FalkorDBAdapter
from src.adapters.memgraph import MemgraphAdapter
from src.adapters.neo4j_db import Neo4jAdapter

ADAPTER_FACTORIES: dict[str, Callable[[], GraphDatabaseAdapter]] = {
    "cognodb": CognoDBAdapter,
    "neo4j": Neo4jAdapter,
    "memgraph": MemgraphAdapter,
    "falkordb": FalkorDBAdapter,
    "arangodb": ArangoDBAdapter,
}

ALL_DATABASES = tuple(ADAPTER_FACTORIES.keys())


def _filled(value: str | None) -> bool:
    if value is None:
        return False
    text = value.strip()
    if not text:
        return False
    upper = text.upper()
    return not (
        upper.startswith("YOUR_")
        or "YOUR_INSTANCE" in upper
        or "YOUR_HOST" in upper
        or upper == "YOUR_PASSWORD"
        or upper == "YOUR_URI"
    )


def credential_status() -> dict[str, dict[str, object]]:
    """Return readiness info without exposing secret values."""
    checks = {
        "cognodb": ["COGNODB_URI", "COGNODB_USERNAME", "COGNODB_PASSWORD"],
        "neo4j": ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"],
        "memgraph": ["MEMGRAPH_URI"],  # username/password optional locally
        "falkordb": ["FALKORDB_HOST"],
        "arangodb": ["ARANGODB_URL", "ARANGODB_USERNAME", "ARANGODB_PASSWORD"],
    }
    status: dict[str, dict[str, object]] = {}
    for name, required in checks.items():
        missing = [key for key in required if not _filled(os.getenv(key))]
        status[name] = {
            "ready": len(missing) == 0,
            "missing": missing,
            "label": "READY" if not missing else "NOT RUN / CREDENTIALS REQUIRED",
        }
    return status


def get_adapter(name: str) -> GraphDatabaseAdapter:
    key = name.lower().strip()
    if key not in ADAPTER_FACTORIES:
        raise ValueError(
            f"Unknown database {name!r}. Supported: {', '.join(ALL_DATABASES)}"
        )
    return ADAPTER_FACTORIES[key]()


def resolve_databases(selection: str) -> list[str]:
    """Parse --database cognodb|neo4j|...|all into a concrete list."""
    text = selection.lower().strip()
    if text == "all":
        return list(ALL_DATABASES)
    parts = [p.strip() for p in text.split(",") if p.strip()]
    unknown = [p for p in parts if p not in ADAPTER_FACTORIES]
    if unknown:
        raise ValueError(f"Unknown database(s): {', '.join(unknown)}")
    return parts
