"""L2 sense retrieval. Needs data/ (WordNet auto-downloads; AoA via
scripts/fetch_aoa.py) — no paid API."""

from __future__ import annotations

import pytest

from crack.l2_senses import aoa_coverage, aoa_lookup, compound_splits, retrieve, senses_for


@pytest.mark.parametrize("lemma,stage", [
    ("bank", "exact"),
    ("ACE", "lowercase"),          # AoA has only "ace"
    ("accredit", "lemmatized"),    # AoA has only "accredited"
    ("assets", "lemmatized"),      # query side lemmatized: AoA has only "asset"
    ("comically", "derived_from_adjective"),  # pertainym comical, not comic + ally
    ("additionally", "miss"),                 # adverb, no pertainym: never split
    ("well-nigh", "derived_from_parts"),      # hyphenated adverb still splits on "-"
    ("porkchop", "derived_from_parts"),       # compound: max(pork, chop)
    ("liquid_assets", "derived_from_parts"),  # MWE: max(liquid, asset)
    ("New_York", "miss"),
])
def test_aoa_fallback_stage(lemma: str, stage: str) -> None:
    aoa, got = aoa_lookup(lemma)
    assert got == stage
    assert (aoa is None) == (stage == "miss")


def test_aoa_coverage_is_cumulative() -> None:
    cov = aoa_coverage(["bank", "ACE", "accredit", "comically", "porkchop", "New_York"])
    assert {k: round(v, 1) for k, v in cov.items()} == {
        "exact": 16.7, "lowercase": 33.3, "lemmatized": 50.0,
        "derived_from_adjective": 66.7, "derived_from_parts": 83.3, "miss": 16.7,
    }


def test_derived_takes_the_later_learned_part() -> None:
    parts = [aoa_lookup(p)[0] for p in ("liquid", "assets")]
    assert aoa_lookup("liquid_assets")[0] == max(parts)


def test_senses_carry_lexname_semcor_and_aoa() -> None:
    senses = senses_for("guts")
    courage = next(s for s in senses if s.sense_id == "backbone.n.02")
    assert courage.lemma == "guts"
    assert courage.lexname == "noun.attribute"
    assert courage.semcor_count == 2
    assert courage.aoa_match == "exact" and courage.aoa_estimate is not None
    assert {"noun.body", "noun.attribute"} <= {s.lexname for s in senses}


def test_compound_split_autobiography_reachable() -> None:
    assert ("auto", "biography") in compound_splits("autobiography")
    # exact lemma names only: "lain" is an inflection of "lie", not a lemma
    assert ("exp", "lain") not in compound_splits("explain")


def test_retrieve_skips_stopwords_and_adds_split_senses() -> None:
    senses = retrieve(["The", "autobiography", "is", "autobiography"])
    assert {s.term for s in senses} == {"autobiography"}
    split = [s for s in senses if s.source == "wordnet_split:auto+biography"]
    assert {s.lemma for s in split} >= {"auto", "biography"}


def test_run_l2_populates_record_from_l1_tokens() -> None:
    from crack.config import DEFAULT_SETTINGS
    from crack.enums import Genre
    from crack.layers import run_l2
    from crack.schema import AnalysisRecord, L1Result

    record = AnalysisRecord(item_id="t", text="The trunk.", target_ages=[8])
    with pytest.raises(ValueError):
        run_l2(record, DEFAULT_SETTINGS)
    record.l1_result = L1Result(genre=Genre.DECLARATIVE, tokens=["The", "trunk"], lemmas=[], pos_tags=[])
    record = run_l2(record, DEFAULT_SETTINGS)
    assert record.l2_result.senses and {s.term for s in record.l2_result.senses} == {"trunk"}
    assert record.trace[-1].layer == "L2"


def test_mwe_scan_handles_reflexive_and_inflection() -> None:
    from crack.l2_senses import mwe_spans
    assert mwe_spans(["Pull", "yourself", "together"]) == [("Pull yourself together", "pull_together")]
    assert ("going after", "go_after") in mwe_spans(["going", "after", "liquid", "assets"])
    assert ("liquid assets", "liquid_assets") in mwe_spans(["going", "after", "liquid", "assets"])


def test_mwe_scan_skips_function_word_only_grams() -> None:
    from crack.l2_senses import mwe_spans
    assert mwe_spans(["at", "all"]) == []  # at_all is a WordNet lemma


def test_retrieve_tags_mwe_senses() -> None:
    senses = retrieve(["liquid", "assets"])
    mwe = [s for s in senses if s.source == "wordnet_mwe:liquid_assets"]
    assert mwe and {s.term for s in mwe} == {"liquid assets"}


@pytest.mark.parametrize("apos", ["'", "’"])
def test_possessives_reach_l2_with_either_apostrophe(apos: str) -> None:
    terms = {s.term for s in retrieve(["the", f"car{apos}s", "trunk", f"don{apos}t"])}
    assert terms == {"car", "trunk"}


def test_adverb_takes_adjective_aoa() -> None:
    assert aoa_lookup("comically")[0] == aoa_lookup("comical")[0]


# Soundalike workstream 02: hyphen groups and alternate senses.
T2 = "Why did the cat stop dating the cad? Because she realized he was only purr-suing her for his own gain!"
T3 = "Why did the cat start working at a bank? Because she wanted to turn her cat-nap into cash."


def _through_l3(text):
    from crack.config import DEFAULT_SETTINGS
    from crack.layers import run_l1, run_l2, run_l3
    from crack.schema import AnalysisRecord

    record = AnalysisRecord(item_id="t", text=text, target_ages=[])
    return run_l3(run_l2(run_l1(record, DEFAULT_SETTINGS), DEFAULT_SETTINGS), DEFAULT_SETTINGS)


def test_hyphen_group_gets_whole_word_and_split_senses() -> None:
    senses = retrieve(["cat", "nap"], text=T3, hyphen_groups=["cat-nap"])
    hyphen = [s for s in senses if s.term == "cat-nap"]
    assert any(s.source == "wordnet" and s.lemma == "catnap" for s in hyphen)
    assert {s.lemma for s in hyphen if s.source == "wordnet_split:cat+nap"} >= {"cat", "nap"}


def test_retrieve_without_hyphen_groups_is_unchanged() -> None:
    assert retrieve(["cat", "nap"], text=T3) == retrieve(["cat", "nap"], text=T3, hyphen_groups=[])


def test_cat_nap_becomes_a_split_candidate() -> None:
    record = _through_l3(T3)
    cand = next(c for c in record.l3_result.candidates if c.term == "cat-nap")
    assert ("cat", "nap") in cand.split_options


def test_alternates_get_senses_but_are_not_ranked_yet() -> None:
    record = _through_l3(T2)
    assert [c.surface for c in record.l2_result.soundalikes][:1] == ["purr-suing"]
    alt = [s for s in record.l2_result.senses if s.source == "soundalike:pursuing"]
    assert alt and all(s.term == "purr-suing" for s in alt)
    terms = [c.term for c in record.l3_result.candidates + record.l3_result.deferred_candidates]
    assert "purr-suing" not in terms  # L3 soundalike entries arrive with workstream 03
