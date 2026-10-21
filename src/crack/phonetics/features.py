"""PanPhon articulatory feature table and weights, read without pandas.

panphon 0.22.2 opens its CSV data with the platform default encoding
(``featuretable.py`` line 83), so ``panphon.FeatureTable()`` raises
``UnicodeDecodeError`` on Windows (cp1252) unless ``PYTHONUTF8=1`` is set.
This module reads the same files explicitly as UTF-8, so the phonetics package
works on every platform without importing ``FeatureTable``.

It also fixes the library's weight misalignment. ``data/feature_weights.csv``
lists 22 weights in a different column order from the 24 features in
``data/ipa_all.csv``; ``panphon.distance.Distance`` zips them by position, so
for example ``tense`` gets 0.125 instead of 0.25. Here weights are matched to
features by name, and features without a weight (``hitone``, ``hireg``) get 0.
"""
from __future__ import annotations

import csv
import unicodedata
from functools import lru_cache
from importlib.util import find_spec
from pathlib import Path

_SPEC_TO_INT = {"+": 1, "0": 0, "-": -1}


def _open_data(name: str):
    # Locate panphon's data without importing panphon (which pulls in pandas).
    spec = find_spec("panphon")
    if spec is None or spec.origin is None:
        raise ModuleNotFoundError("panphon is required for crack.phonetics (pip install panphon==0.22.2)")
    return (Path(spec.origin).parent / "data" / name).open(encoding="utf-8", newline="")


def normalize(segment: str) -> str:
    """PanPhon keys its segment table by NFD-normalized IPA."""
    return unicodedata.normalize("NFD", segment)


@lru_cache(maxsize=1)
def _table() -> tuple[tuple[str, ...], dict[str, tuple[int, ...]]]:
    with _open_data("ipa_all.csv") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        names = tuple(header[1:])
        segments = {
            normalize(row[0]): tuple(_SPEC_TO_INT[value] for value in row[1:])
            for row in reader
            if row
        }
    return names, segments


@lru_cache(maxsize=1)
def _weight_file() -> tuple[tuple[str, ...], tuple[float, ...]]:
    with _open_data("feature_weights.csv") as handle:
        rows = list(csv.reader(handle))
    return tuple(rows[0]), tuple(float(value) for value in rows[1])


def feature_names() -> tuple[str, ...]:
    """The 24 feature names, in ipa_all.csv column order (the vector order)."""
    return _table()[0]


@lru_cache(maxsize=1)
def feature_weights() -> dict[str, float]:
    """Weight for each feature, matched BY NAME; unweighted features get 0.0."""
    by_name = dict(zip(*_weight_file()))
    return {name: by_name.get(name, 0.0) for name in feature_names()}


def weight_vector() -> tuple[float, ...]:
    """Name-aligned weights in vector order."""
    weights = feature_weights()
    return tuple(weights[name] for name in feature_names())


def positional_weight_pairs() -> list[tuple[str, float]]:
    """Reproduce panphon's misalignment: zip weights against names by position.

    Only used to document and regression-test the upstream bug.
    """
    return list(zip(feature_names(), _weight_file()[1]))


def segment_vector(segment: str) -> tuple[int, ...]:
    """Feature vector (+1/0/-1 per feature) for one IPA segment."""
    try:
        return _table()[1][normalize(segment)]
    except KeyError:
        raise KeyError(f"IPA segment {segment!r} is not in panphon's ipa_all.csv") from None


def has_segment(segment: str) -> bool:
    return normalize(segment) in _table()[1]
