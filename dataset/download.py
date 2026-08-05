"""Download the public SNAP cit-HepPh citation network.

Source page: https://snap.stanford.edu/data/cit-HepPh.html
File URL:    https://snap.stanford.edu/data/cit-HepPh.txt.gz

This module downloads the archive into dataset/raw/ only.
It does not invent synthetic production data.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import requests

DATASET_NAME = "cit-HepPh"
DATASET_PAGE = "https://snap.stanford.edu/data/cit-HepPh.html"
DOWNLOAD_URL = "https://snap.stanford.edu/data/cit-HepPh.txt.gz"
RAW_FILENAME = "cit-HepPh.txt.gz"

# Optional integrity check against the SNAP archive used in this suite.
EXPECTED_SHA256 = "917e77b3344aed33fd2d849443c9512b7c528b9dc87251d4245fb3777bbe4128"

DEFAULT_TIMEOUT_SECONDS = 120
CHUNK_SIZE = 1024 * 256


def default_raw_dir(project_root: Path | None = None) -> Path:
    root = project_root or Path(__file__).resolve().parents[1]
    return root / "dataset" / "raw"


def download_file(
    url: str = DOWNLOAD_URL,
    dest_path: Path | None = None,
    *,
    force: bool = False,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Path:
    """Download the SNAP archive to dest_path. Skip if already present unless force."""
    path = dest_path or (default_raw_dir() / RAW_FILENAME)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.is_file() and path.stat().st_size > 0 and not force:
        return path

    tmp_path = path.with_suffix(path.suffix + ".partial")
    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with tmp_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    handle.write(chunk)
    tmp_path.replace(path)

    if EXPECTED_SHA256 is not None:
        digest = sha256_file(path)
        if digest != EXPECTED_SHA256:
            path.unlink(missing_ok=True)
            raise ValueError(
                f"SHA-256 mismatch for {path.name}: got {digest}, "
                f"expected {EXPECTED_SHA256}"
            )

    return path


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main() -> int:
    path = download_file()
    size_bytes = path.stat().st_size
    print(f"Downloaded: {path}")
    print(f"Size bytes: {size_bytes}")
    print(f"SHA-256   : {sha256_file(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
