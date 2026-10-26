"""Phonetic core (handoff 01): graded sound similarity, offline and local.

Needs pinned official lexical data (see scripts/fetch_lexical_resources.py). Values are
pinned to what docs/soundalike/reference_wlev_fixed.py prints; see the checks
table in docs/soundalike/handoff/01_phonetic_core.md.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

from crack.phonetics import (
    FEATURE_WEIGHTS,
    MissingPronunciation,
    calibrate,
    phone_distance,
    pronunciations,
    sound_similarity,
)
from crack.phonetics import calibration, features, lexicon
from crack.phonetics.similarity import score_pronunciations

ROOT = Path(__file__).resolve().parents[1]
PHONETICS_SRC = ROOT / "src" / "crack" / "phonetics"

SIX_PAIRS = {
    ("knight", "night"): 1.000,
    ("cat", "cad"): 0.994,
    ("bat", "pat"): 0.994,
    ("pat", "pit"): 0.966,
    ("cat", "cash"): 0.954,
    ("drum", "drama"): 0.890,
}


def vec(segment: str):
    return features.segment_vector(segment)


# 1. Name-aligned weights
def test_feature_weights_are_aligned_by_name():
    assert FEATURE_WEIGHTS["tense"] == 0.25
    assert FEATURE_WEIGHTS["long"] == 0.125
    assert FEATURE_WEIGHTS["velaric"] == 0.25
    assert FEATURE_WEIGHTS["hitone"] == FEATURE_WEIGHTS["hireg"] == 0
    assert sum(FEATURE_WEIGHTS.values()) == pytest.approx(7.25)
    assert len(FEATURE_WEIGHTS) == 24


# 2. The upstream bug, reproduced as a regression guard
def test_panphon_positional_weights_are_misaligned():
    positional = dict(features.positional_weight_pairs())
    assert positional["tense"] == 0.125  # library gives tense the weight of "long"
    cost = lambda weights: sum(w * abs(a - b) for w, a, b in zip(weights, vec("æ"), vec("ɪ")))
    assert cost([w for _, w in features.positional_weight_pairs()]) == pytest.approx(1.25)
    assert cost(features.weight_vector()) == pytest.approx(1.5)


def test_panphon_library_itself_shows_the_bug():
    distance = pytest.importorskip("panphon.distance")
    try:
        lib = distance.Distance()
    except UnicodeDecodeError:  # panphon 0.22.2 on Windows without PYTHONUTF8
        pytest.skip("panphon.FeatureTable cannot read its CSVs under this locale")
    assert lib.weighted_substitution_cost(list(vec("æ")), list(vec("ɪ"))) == pytest.approx(1.25)


# 3. δ table
@pytest.mark.parametrize("a,b,expected", [
    ("t", "d", 0.0172), ("b", "p", 0.0172), ("ʌ", "ɑ", 0.0517),
    ("æ", "ɪ", 0.1034), ("t", "ʃ", 0.1379), ("m", "ə", 0.4828),
])
def test_phone_distance_table(a, b, expected):
    assert round(phone_distance(vec(a), vec(b)), 4) == expected


def test_phone_distance_is_graded_not_binary():
    values = {round(phone_distance(vec(a), vec(b)), 4) for a, b in
              [("t", "d"), ("æ", "ɪ"), ("t", "ʃ"), ("m", "ə")]}
    assert len(values) == 4 and all(0 < v < 1 for v in values)


# 4. Six required pairs and their ordering
@pytest.mark.parametrize("pair,expected", SIX_PAIRS.items())
def test_six_required_pairs(pair, expected):
    assert round(sound_similarity(*pair).sim, 3) == expected


def test_six_pair_ordering():
    s = {pair: sound_similarity(*pair).sim for pair in SIX_PAIRS}
    assert s[("knight", "night")] > s[("cat", "cad")] == s[("bat", "pat")] > s[("pat", "pit")]
    assert s[("pat", "pit")] > s[("cat", "cash")] > s[("drum", "drama")]


# 5. Indel sensitivity
def test_indel_one_only_changes_unequal_lengths():
    for pair, expected in SIX_PAIRS.items():
        got = round(sound_similarity(*pair, indel=1.0).sim, 3)
        assert got == (0.790 if pair == ("drum", "drama") else expected)


# 6. Lexicon source and entries
@pytest.mark.parametrize("word,entry", [
    ("cat", "K AE1 T"), ("cad", "K AE1 D"), ("cash", "K AE1 SH"),
    ("drum", "D R AH1 M"), ("drama", "D R AA1 M AH0"), ("knight", "N AY1 T"),
    ("night", "N AY1 T"), ("bat", "B AE1 T"), ("pat", "P AE1 T"), ("pit", "P IH1 T"),
])
def test_official_cmudict_first_entries(word, entry):
    assert lexicon._cmu()[word][0] == entry.split()


def test_stress_stripped_but_reduced_vowels_kept():
    assert pronunciations("drama") == [("D", "R", "AA", "M", "AH0")]


def test_er_is_not_dropped():
    # The reference script maps ER to ɝ, which panphon silently drops.
    assert len(lexicon.to_feature_vectors(("P", "ER"))) == 2


def test_hyphenated_coinage_and_spans():
    assert sound_similarity("purr-suing", "pursuing").sim == pytest.approx(1.0)
    assert round(sound_similarity("lettuce", ["let", "us"]).sim, 3) == 0.993
    assert lexicon.lookup_source("pursuing") == "cmudict"
    assert lexicon.lookup_source("xqzzt") == "missing"
    with pytest.raises(MissingPronunciation):
        sound_similarity("xqzzt", "cat")


# 7. Max over pronunciations
def test_best_pronunciation_pair_is_used():
    score = sound_similarity("wok", "walk")
    assert score.sim == 1.0
    assert score.pron_pair == (("W", "AA", "K"), ("W", "AA", "K"))
    assert round(score_pronunciations(("W", "AO", "K"), ("W", "AA", "K")).sim, 3) == 0.960


# 8. Calibration
def test_calibration_endpoints():
    for length in calibration.stored_lengths():
        mu = calibration.baseline_mean(length)
        assert calibrate(mu, length) == pytest.approx(0.0)
        assert calibrate(1.0, length) == pytest.approx(1.0)


def test_calibration_table_is_committed_and_ordered():
    table = calibration.calibration_table()
    from crack.lexical_resources import resource_manifest
    assert table["lexicon"] == "cmusphinx/cmudict"
    assert table["lexicon_version"] == resource_manifest()["resources"]["cmudict"]["version"]
    assert table["lexicon_sha256"] == resource_manifest()["resources"]["cmudict"]["sha256"]
    for row in table["lengths"].values():
        assert 0 < row["mean"] < row["p95"] < row["p99"] < 1


# 9. Determinism, no providers
def test_deterministic_and_local():
    assert sound_similarity("drum", "drama") == sound_similarity("drum", "drama")
    for path in PHONETICS_SRC.glob("*.py"):
        assert "providers" not in path.read_text(encoding="utf-8"), path.name


# 10. Windows: never construct panphon.FeatureTable (it fails under cp1252)
def test_does_not_use_panphon_featuretable(monkeypatch):
    featuretable = pytest.importorskip("panphon.featuretable")

    def refuse(*args, **kwargs):
        raise AssertionError("crack.phonetics must not construct panphon.FeatureTable")

    monkeypatch.setattr(featuretable.FeatureTable, "__init__", refuse)
    for cache in (features._table, features._weight_file, features.feature_weights):
        cache.cache_clear()
    assert round(sound_similarity("cat", "cash").sim, 3) == 0.954


# 11. Licence
def test_no_gpl_cmudict_dependency():
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    assert "panphon==0.22.2" in deps
    assert not any(re.match(r"cmudict\b", d) for d in deps)
    for path in PHONETICS_SRC.glob("*.py"):
        assert not re.search(r"^\s*(import cmudict|from cmudict)", path.read_text(encoding="utf-8"), re.M)


# Resume fingerprint must see the subpackage (handoff 03, test 11)
def test_run_fingerprint_covers_phonetics(tmp_path):
    from crack.config import Settings
    from crack.runner import _run_fingerprint

    blind = tmp_path / "blind.jsonl"
    blind.write_text("{}\n", encoding="utf-8")
    sources = _run_fingerprint(blind, Settings())["source_sha256"]
    assert "phonetics/similarity.py" in sources and "phonetics/lexicon.py" in sources


# Segmentation parity with the reference script (handoff 01, Risks)
def test_segmentation_matches_reference_except_er():
    panphon = pytest.importorskip("panphon")
    try:
        ft = panphon.FeatureTable()
    except UnicodeDecodeError:
        pytest.skip("panphon.FeatureTable cannot read its CSVs under this locale")
    reference = {"AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ", "EH": "ɛ",
                 "EY": "eɪ", "IH": "ɪ", "IY": "i", "OW": "oʊ", "OY": "ɔɪ", "UH": "ʊ", "UW": "u",
                 "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "F": "f", "G": "ɡ", "HH": "h", "JH": "dʒ",
                 "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ", "P": "p", "R": "ɹ", "S": "s",
                 "SH": "ʃ", "T": "t", "TH": "θ", "V": "v", "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ"}
    words = ["chess", "judge", "boy", "cow", "propane", "profane", "alleged", "toy", "house", "rhythm"]
    for word in words:
        arpa = pronunciations(word)[0]
        ipa = "".join("ə" if p == "AH0" else reference[p] for p in arpa)
        assert lexicon.to_feature_vectors(arpa) == [tuple(v) for v in ft.word_to_vector_list(ipa, numeric=True)], word
