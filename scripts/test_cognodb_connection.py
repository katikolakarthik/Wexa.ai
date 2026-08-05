#!/usr/bin/env python3
"""Phase 1: verify CognoDB Cloud connectivity via Neo4j Python driver.

Loads credentials from environment variables (typically via .env):

  COGNODB_URI
  COGNODB_USERNAME
  COGNODB_PASSWORD

Never prints passwords.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j.exceptions import Neo4jError, ServiceUnavailable, AuthError

# Ensure project root is on sys.path when running as a script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.cognodb import CognoDBAdapter, describe_neo4j_error


def main() -> int:
    env_path = PROJECT_ROOT / ".env"
    load_dotenv(dotenv_path=env_path)

    adapter = CognoDBAdapter()

    print("CognoDB connectivity test")
    print("-------------------------")
    print(f"Project root : {PROJECT_ROOT}")
    print(f".env loaded  : {env_path.is_file()}")
    # Safe diagnostics only — never print password.
    print(f"URI set      : {bool(adapter.uri)}")
    print(f"Username set : {bool(adapter.username)}")
    print(f"Password set : {bool(adapter.password)}")
    if adapter.uri:
        print(f"URI host     : {adapter.uri}")

    try:
        adapter.connect()
        ok = adapter.ping()
        if not ok:
            print("FAILURE: Connected, but RETURN 1 AS result did not return 1.")
            return 1
        print("SUCCESS: Connected to CognoDB and executed RETURN 1 AS result.")
        return 0
    except ValueError as exc:
        print(f"FAILURE: {exc}")
        return 1
    except AuthError as exc:
        print(f"FAILURE: Authentication failed. {describe_neo4j_error(exc)}")
        print("Check COGNODB_USERNAME and COGNODB_PASSWORD in .env.")
        return 1
    except ServiceUnavailable as exc:
        print(f"FAILURE: Service unavailable. {exc}")
        print("Check COGNODB_URI scheme/host and that the instance is running.")
        return 1
    except Neo4jError as exc:
        print(f"FAILURE: Neo4j/Bolt error. {describe_neo4j_error(exc)}")
        return 1
    except Exception as exc:  # noqa: BLE001 — surface unexpected connect errors clearly
        print(f"FAILURE: Unexpected error ({type(exc).__name__}): {exc}")
        return 1
    finally:
        adapter.close()


if __name__ == "__main__":
    raise SystemExit(main())
