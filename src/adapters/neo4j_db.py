"""Neo4j adapter (Aura / self-hosted) via official Neo4j Python driver."""

from __future__ import annotations

from typing import Any

from src.adapters.bolt_cypher import BoltCypherAdapter


class Neo4jAdapter(BoltCypherAdapter):
    name = "neo4j"
    dialect = "neo4j"

    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        super().__init__(
            uri_env="NEO4J_URI",
            username_env="NEO4J_USERNAME",
            password_env="NEO4J_PASSWORD",
            uri=uri,
            username=username,
            password=password,
        )

    def get_resource_info(self) -> dict[str, Any]:
        info = super().get_resource_info()
        info.update(
            {
                "deployment": "neo4j_aura_or_self_hosted",
                "notes": (
                    "Document exact Aura tier / self-hosted CPU+RAM in README. "
                    "Do not claim parity with CognoDB c0 (0.5 burst vCPU / 512 MB) "
                    "unless independently verified."
                ),
            }
        )
        return info
