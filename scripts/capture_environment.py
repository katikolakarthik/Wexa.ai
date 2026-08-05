#!/usr/bin/env python3
"""Capture client environment snapshot (no secrets)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics.system import format_environment_markdown


def main() -> int:
    out = PROJECT_ROOT / "results" / "ENVIRONMENT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(format_environment_markdown(), encoding="utf-8")
    print(f"SUCCESS: Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
