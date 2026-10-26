"""Pinned official lexical data, downloaded explicitly and verified before use.

The manifest is part of the source distribution. Large data files stay in the
local data cache. No model call or implicit network fallback occurs here.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

RESOURCE_DATA = Path(__file__).with_name("resource_data")
MANIFEST_PATH = RESOURCE_DATA / "manifest.json"
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "lexical_resources"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def resource_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=2)
def resource_directory(name: str) -> Path:
    """Require the exact manifest snapshot, including every extracted file."""
    resource = resource_manifest()["resources"][name]
    root = CACHE_DIR / resource["directory"]
    expected = dict(resource["files"])
    if name == "oewn":
        expected["lexnames"] = sha256(RESOURCE_DATA / "lexnames.txt")
    for filename, checksum in expected.items():
        path = root / filename
        if not path.is_file() or sha256(path) != checksum:
            raise LookupError(
                f"Missing or modified {resource['name']} data: {path}. "
                "Run: python scripts/fetch_lexical_resources.py"
            )
    return root


def resource_provenance() -> dict:
    """Serializable identities for run metadata and resume compatibility."""
    resources = resource_manifest()["resources"]
    root = CACHE_DIR.parent
    return {
        "manifest_sha256": sha256(MANIFEST_PATH),
        "resources": {name: {key: row[key] for key in ("name", "version", "sha256", "url")}
                      for name, row in resources.items()},
        "phonetic_calibration_sha256": sha256(root / "phonetic_calibration.json"),
        "aoa_sha256": sha256(root / "aoa_kuperman.csv") if (root / "aoa_kuperman.csv").exists() else None,
        "semcor_reference": "Princeton WordNet 3.0 cntlist.rev, exact lemma sense keys",
    }
