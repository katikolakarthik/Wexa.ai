"""Registry and credential gating tests (no live cloud calls)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.registry import ALL_DATABASES, get_adapter, resolve_databases


def test_all_databases_registered():
    assert set(ALL_DATABASES) == {
        "cognodb",
        "neo4j",
        "memgraph",
        "falkordb",
        "arangodb",
    }


def test_get_adapter_constructs_without_connect():
    for name in ALL_DATABASES:
        adapter = get_adapter(name)
        assert adapter.name == name


def test_resolve_databases_all_and_csv():
    assert resolve_databases("all") == list(ALL_DATABASES)
    assert resolve_databases("neo4j,memgraph") == ["neo4j", "memgraph"]
