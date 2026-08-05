#!/usr/bin/env python3
"""One-off FalkorDB connectivity probe (no secrets printed)."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=True)

from src.adapters.falkordb import FalkorDBAdapter


def main() -> int:
    adapter = FalkorDBAdapter()
    print(f"host={adapter.host}", flush=True)
    print(f"port={adapter.port}", flush=True)
    print(f"ssl={adapter.ssl}", flush=True)
    print(f"username_set={bool(adapter.username)}", flush=True)
    print(f"graph={adapter.graph_name}", flush=True)
    try:
        adapter.connect()
        ok = adapter.ping()
        print(f"ping={ok}", flush=True)
        print("SUCCESS: Connected to FalkorDB.", flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAILURE: {type(exc).__name__}: {exc}", flush=True)
        return 1
    finally:
        adapter.close()


if __name__ == "__main__":
    raise SystemExit(main())
