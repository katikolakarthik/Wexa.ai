"""Client-side system / environment snapshots.

Never includes credentials or connection passwords.
"""

from __future__ import annotations

import platform
import socket
from datetime import datetime, timezone
from typing import Any

import psutil


def client_resource_snapshot() -> dict[str, Any]:
    """Observable client-machine footprint at call time."""
    vm = psutil.virtual_memory()
    proc = psutil.Process()
    with proc.oneshot():
        mem_info = proc.memory_info()
        cpu_percent = proc.cpu_percent(interval=0.1)
    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "os": platform.platform(),
        "python_version": platform.python_version(),
        "processor": platform.processor() or "not observable",
        "cpu_logical_count": psutil.cpu_count(logical=True) or "not observable",
        "cpu_physical_count": psutil.cpu_count(logical=False) or "not observable",
        "client_ram_total_mb": round(vm.total / (1024 * 1024), 1),
        "client_ram_available_mb": round(vm.available / (1024 * 1024), 1),
        "client_ram_used_percent": vm.percent,
        "process_rss_mb": round(mem_info.rss / (1024 * 1024), 1),
        "process_cpu_percent": cpu_percent,
        "notes": (
            "Client-side only. Remote DB vCPU/RAM remain 'not observable' "
            "unless verified in each vendor console."
        ),
    }


def format_environment_markdown(snapshot: dict[str, Any] | None = None) -> str:
    data = snapshot or client_resource_snapshot()
    lines = [
        "# Client benchmark environment",
        "",
        "Captured automatically. Contains no database passwords.",
        "",
        "| Field | Value |",
        "|-------|-------|",
    ]
    for key, value in data.items():
        lines.append(f"| `{key}` | {value} |")
    lines.append("")
    return "\n".join(lines)
