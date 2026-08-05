"""Memgraph adapter via Neo4j-compatible Bolt driver.

Memgraph Cloud (and gqlalchemy with encrypted=True) requires TLS.
Use a `bolt+s://HOST:7687` URI — plain `bolt://` often fails with an
incomplete handshake against cloud endpoints.
"""

from __future__ import annotations

from typing import Any

from src.adapters.bolt_cypher import BoltCypherAdapter


class MemgraphAdapter(BoltCypherAdapter):
    name = "memgraph"
    dialect = "memgraph"

    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        super().__init__(
            uri_env="MEMGRAPH_URI",
            username_env="MEMGRAPH_USERNAME",
            password_env="MEMGRAPH_PASSWORD",
            uri=uri,
            username=username,
            password=password,
        )
        # Cloud instances expect TLS. Memgraph Cloud often presents a self-signed
        # cert (gqlalchemy encrypted=True). Prefer bolt+ssc over plain bolt.
        if self.uri.startswith("bolt://") and not self.uri.startswith(
            ("bolt+s://", "bolt+ssc://")
        ):
            self.uri = "bolt+ssc://" + self.uri[len("bolt://") :]
        elif self.uri.startswith("bolt+s://"):
            # If verify fails against self-signed cloud certs, callers may set
            # bolt+ssc:// explicitly. Keep bolt+s when user chose it.
            pass

    def get_resource_info(self) -> dict[str, Any]:
        info = super().get_resource_info()
        info.update(
            {
                "deployment": "memgraph_cloud_or_self_hosted",
                "notes": (
                    "Memgraph Cloud needs TLS (bolt+ssc for self-signed certs), "
                    "matching gqlalchemy encrypted=True. "
                    "Local Docker may use plain bolt:// with empty auth. "
                    "Document cloud/self-hosted vCPU/RAM before claiming fairness."
                ),
            }
        )
        return info
