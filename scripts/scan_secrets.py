"""Offline secret/placeholder scan for submission validation (prints REDACTED only)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "__pycache__", "charts"}
SKIP_SUFFIX = {".png", ".pyc"}

PATTERNS = {
    "password_assign": re.compile(
        r"password\s*[=:]\s*[\"']?([^\s\"',;]+)", re.IGNORECASE
    ),
    "uri_userinfo": re.compile(
        r"(?:bolt\+s?s?c?://|neo4j\+s://|redis://)[^\s/:]+:[^@\s]+@[^\s]+",
        re.IGNORECASE,
    ),
    "jwtish": re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"),
    "sk_token": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "live_host_uri": re.compile(
        r"(?:bolt\+s?s?c?://|neo4j\+s://)(?!YOUR_|HOST|xxxx)[a-zA-Z0-9][a-zA-Z0-9.\-]{6,}",
        re.IGNORECASE,
    ),
}

ALLOWED_PW = {
    "YOUR_PASSWORD",
    "",
    "***",
    "optional",
    "password",
    "PASSWORD",
    "instance",
    "super-secret",
    "hunter2",
    "secret",
    "none",
    "empty",
    "from",
    "None",
}


def main() -> int:
    findings: list[tuple[str, str, str, str]] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix in SKIP_SUFFIX:
            continue
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        if path.name == ".env":
            findings.append(("LOCAL_ENV", rel, "file", "present_gitignored_REDACTED"))
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name, rx in PATTERNS.items():
            for match in rx.finditer(text):
                val = match.group(0)
                if "YOUR_" in val or "xxxx" in val or "example.com" in val:
                    continue
                if name == "password_assign":
                    pw = match.group(1)
                    if (
                        pw.upper().startswith("YOUR_")
                        or pw in ALLOWED_PW
                        or pw.startswith("{")
                        or "getenv" in pw.lower()
                    ):
                        continue
                line_no = text.count("\n", 0, match.start()) + 1
                line = text.splitlines()[line_no - 1] if text else ""
                if "getenv" in line or "os.environ" in line or "fieldnames" in line:
                    continue
                if name == "live_host_uri" and (
                    "YOUR_" in line or "HOST" in line or "xxxx" in line
                ):
                    continue
                findings.append((name, rel, f"line:{line_no}", "REDACTED"))

    print(f"FINDINGS {len(findings)}")
    for item in findings:
        print("|".join(item))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
