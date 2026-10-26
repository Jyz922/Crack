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
    # Inspect both retrieval paths without the production top-four cap:
    # additional exact homophones may legitimately displace a near pair.
    cands = found(T2, Settings(SOUNDALIKE_MAX_CANDIDATES=20))
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
    assert any(a.form == "cat" and round(a.sim, 3) == 0.954 and a.source == "in_text"
               for a in cands["cash"].alternates)
    assert any(a.form == "cache" and a.sim == 1.0 and a.source == "lexicon"
               for a in cands["cash"].alternates)
    # "cat-nap" joined is "catnap": resegmentation (L2/L3), not a soundalike.
    assert all(a.form != "catnap" for c in cands.values() for a in c.alternates)


def test_hard_negative_is_reported_not_judged():
    # cat/cad is the closest pair in text 2 and is not the pun; the finder
    # reports it with its score and leaves selection to L4.
    cands = found(T2, Settings(SOUNDALIKE_MAX_CANDIDATES=20))
    assert cands["cad"].alternates[0].sim > cands["purr-suing"].alternates[0].sim - 0.01


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


@pytest.mark.parametrize("word,alternate", [("Whey", "way"), ("Knead", "need"), ("Stationery", "stationary")])
def test_content_word_retrieves_absent_exact_homophone(word, alternate):
    cand = found(word)[word]
    alt = next(a for a in cand.alternates if a.form == alternate)
    assert alt.source == "lexicon" and alt.sim == 1.0
    assert cand.mechanism == "sound_substitution"


def test_exact_lookup_excludes_non_dictionary_and_near_matches(monkeypatch):
    import crack.l3_soundalikes as finder
    monkeypatch.setattr(finder, "_reverse_index", lambda: {("W", "EY"): ("way", "wey", "weigh", "zqzz")})
    monkeypatch.setattr(finder, "_in_wordnet", lambda form: form == "way")
    alts = finder._word_homophones("Whey", 3)[0].alternates
    assert [a.form for a in alts] == ["way"]
    assert finder._word_homophones("cat", 3) == []  # no near-neighbor expansion


def test_exact_lookup_requires_same_reduced_vowels(monkeypatch):
    import crack.l3_soundalikes as finder
    monkeypatch.setattr(finder, "pronunciations", lambda word: [("AH0",)] if word == "alpha" else [("AH",)])
    monkeypatch.setattr(finder, "_reverse_index", lambda: {("AH",): ("omega",)})
    monkeypatch.setattr(finder, "_in_wordnet", lambda word: True)
    assert finder._word_homophones("alpha", 3) == []


def test_exact_lookup_does_not_duplicate_in_text_pair():
    cands = found("Knead need")
    assert all(not (a.form == "need" and a.source == "lexicon") for c in cands.values() for a in c.alternates)
    assert all(not (a.form == "knead" and a.source == "lexicon") for c in cands.values() for a in c.alternates)


def test_merged_candidate_slots_and_alternate_limits():
    cands = found(T3, Settings(SOUNDALIKE_MAX_CANDIDATES=2, SOUNDALIKE_MAX_ALTERNATES=1))
    assert len(cands) <= 2 and all(len(c.alternates) <= 1 for c in cands.values())
    assert len({c.char_span for c in cands.values()}) == len(cands)
