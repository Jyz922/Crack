"""Fetch checksum-pinned official CMUdict and Open English Wordnet snapshots.

Run once after installation, before offline tests: python scripts/fetch_lexical_resources.py
"""
from __future__ import annotations

import argparse
import hashlib
import io
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from crack.lexical_resources import CACHE_DIR, RESOURCE_DATA, resource_manifest


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    temporary.replace(path)


def install_resource(name: str, payload: bytes) -> Path:
    """Check the archive and all members before changing the local cache."""
    spec = resource_manifest()["resources"][name]
    if hashlib.sha256(payload).hexdigest() != spec["sha256"]:
        raise ValueError(f"{name}: download checksum mismatch; no files installed")
    if spec["format"] == "zip":
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            files = {filename: archive.read(spec["archive_prefix"] + filename)
                     for filename in spec["files"]}
    else:
        files = {"cmudict.dict": payload}
    for filename, content in files.items():
        if Path(filename).name != filename or hashlib.sha256(content).hexdigest() != spec["files"][filename]:
            raise ValueError(f"{name}: invalid archive member {filename!r}; no files installed")
    if name == "oewn":
        files["lexnames"] = (RESOURCE_DATA / "lexnames.txt").read_bytes()
    directory = CACHE_DIR / spec["directory"]
    for filename, content in files.items():
        _write(directory / filename, content)
    return directory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--resource", choices=("cmudict", "oewn", "all"), default="all")
    args = parser.parse_args()
    resources = resource_manifest()["resources"]
    for name, spec in resources.items():
        if args.resource not in ("all", name):
            continue
        with urllib.request.urlopen(spec["url"], timeout=60) as response:
            payload = response.read(64 * 1024 * 1024 + 1)
        if len(payload) > 64 * 1024 * 1024:
            raise ValueError(f"{name}: unexpectedly large download")
        print(f"{spec['name']} {spec['version']}: {install_resource(name, payload)}")
    if args.resource in ("all", "oewn"):
        # Prepare historical counts before offline tests disable the network.
        from crack.l2_senses import _legacy_wordnet
        _legacy_wordnet()
        print("Historical WordNet 3.0 SemCor count reference: verified")


if __name__ == "__main__":
    main()
