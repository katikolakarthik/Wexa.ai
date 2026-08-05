#!/usr/bin/env python3
"""Probe connectivity for every configured database adapter.

Never prints passwords.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.registry import ALL_DATABASES, credential_status, get_adapter


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    status = credential_status()

    print("Database credential / connectivity status")
    print("-----------------------------------------")
    exit_code = 0

    for name in ALL_DATABASES:
        info = status[name]
        print(f"\n[{name}] {info['label']}")
        if not info["ready"]:
            print(f"  missing env: {', '.join(info['missing'])}")
            continue

        adapter = get_adapter(name)
        try:
            adapter.connect()
            ok = adapter.ping() if hasattr(adapter, "ping") else True
            if ok:
                print("  SUCCESS: connected and ping OK")
            else:
                print("  FAILURE: connected but ping failed")
                exit_code = 1
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILURE: {type(exc).__name__}: {exc}")
            exit_code = 1
        finally:
            adapter.close()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
