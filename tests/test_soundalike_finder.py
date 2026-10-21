"""Soundalike finder (handoff 02): recall-stage candidates with graded scores.

Offline and local: no provider is imported. Phonetic values are pinned to the
phonetic core's observed output (tests/test_phonetics.py).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from crack.config import DEFAULT_SETTINGS, Settings
from crack.l1_surface import analyze
from crack.l3_soundalikes import _same_family, find_soundalikes

T1 = "When the band broke up, it wasn’t drama — it was just drum!"
T2 = "Why did the cat stop dating the cad? Because she realized he was only purr-suing her for his own gain!"
T3 = "Why did the cat start working at a bank? Because she wanted to turn her cat-nap into cash."


def found(text, settings=DEFAULT_SETTINGS):
    return {c.surface: c for c in find_soundalikes(analyze(text), text, settings)}


def test_spans_index_the_analysed_text():
    for text in (T1, T2, T3):
        for cand in found(text).values():
            assert text[slice(*cand.char_span)] == cand.surface


def test_text2_hyphen_merge_and_in_text_pair():
    cands = found(T2)
    merge = cands["purr-suing"]
    assert merge.mechanism == "sound_substitution"
    assert [(a.form, a.source, a.sim) for a in merge.alternates] == [("pursuing", "hyphen_merge", 1.0)]
    pair = cands["cad"]
    assert pair.mechanism == "sound_pair"
    assert (pair.alternates[0].form, round(pair.alternates[0].sim, 3)) == ("cat", 0.994)


def test_text1_in_text_pair():
    cand = found(T1)["drum"]
    assert cand.mechanism == "sound_pair"
    assert (cand.alternates[0].form, round(cand.alternates[0].sim, 3)) == ("drama", 0.890)


def test_text3_in_text_pair_and_no_self_merge():
    cands = found(T3)
    assert (cands["cash"].alternates[0].form, round(cands["cash"].alternates[0].sim, 3)) == ("cat", 0.954)
    # "cat-nap" joined is "catnap": resegmentation (L2/L3), not a soundalike.
    assert all(a.form != "catnap" for c in cands.values() for a in c.alternates)


def test_hard_negative_is_reported_not_judged():
    # cat/cad is the closest pair in text 2 and is not the pun; the finder
    # reports it with its score and leaves selection to L4.
    assert found(T2)["cad"].alternates[0].sim > found(T2)["purr-suing"].alternates[0].sim - 0.01


def test_word_families_are_not_sound_pairs():
    assert _same_family("camper", "camp") and _same_family("brought", "bring")
    assert _same_family("prescription", "prescribe") and _same_family("school", "schools")
    assert not _same_family("drum", "drama") and not _same_family("cat", "cad")


def test_settings_limit_output():
    assert find_soundalikes(analyze(T2), T2, Settings(SOUNDALIKE_MAX_CANDIDATES=0)) == []
    assert len(find_soundalikes(analyze(T2), T2, Settings(SOUNDALIKE_MAX_CANDIDATES=1))) == 1
    # drum/drama is below the 99th random-pair percentile for length 5.
    assert "drum" not in found(T1, Settings(PHONETIC_RETRIEVE_PERCENTILE="p99"))


def test_finder_is_local():
    src = (Path(__file__).resolve().parents[1] / "src/crack/l3_soundalikes.py").read_text(encoding="utf-8")
    assert "providers" not in src
