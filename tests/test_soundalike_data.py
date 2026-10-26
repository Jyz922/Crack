"""Soundalike evaluation corpus (handoff 04): schema and integrity only.

These check the AUTHORING labels. Validated counts come from blind double
labelling (docs/soundalike/labelling/), which is not run by this test.
"""
from __future__ import annotations

import json
import pytest
from collections import Counter
from pathlib import Path

from crack.corpus import load_blind, load_gold
from crack.enums import MainClassification

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
ITEMS = [json.loads(l) for l in (CORPUS / "soundalike_items.jsonl").read_text(encoding="utf-8").splitlines() if l]


def test_ids_unique_and_files_agree():
    ids = [r["id"] for r in ITEMS]
    assert len(ids) == len(set(ids))
    blind = load_blind(CORPUS / "soundalike_blind.jsonl")
    gold = load_gold(CORPUS / "soundalike_gold.jsonl")
    assert [b.id for b in blind] == ids and set(gold) == set(ids)
    assert all(b.text == r["text"] for b, r in zip(blind, ITEMS))


def test_seed_slice_meets_the_instructor_minimum():
    seed = Counter("neg" if r["neg_type"] else "pos" for r in ITEMS if r["slice"] == "seed")
    assert seed["pos"] >= 20 and seed["neg"] >= 20


def test_negatives_are_typed_minimal_pairs():
    positives = {r["id"]: r for r in ITEMS if r["neg_type"] is None}
    for r in ITEMS:
        if r["neg_type"] is None:
            continue
        assert r["neg_type"] in {"A", "B", "C", "D", "E"}, r["id"]
        assert r["pair_id"] in positives, r["id"]
        assert r["slice"] == positives[r["pair_id"]]["slice"], r["id"]
        assert r["label"] == MainClassification.ONE_SENSE_ONLY.value


def test_positives_name_a_present_pun_word_and_a_target():
    for r in ITEMS:
        if r["neg_type"] is None:
            assert r["pun_word"].lower() in r["text"].lower(), r["id"]
            assert r["target_word"] and r["mechanism"] in {"sound_substitution", "sound_pair", "resegmentation"}


def test_test_texts_are_a_separate_slice():
    tests = {r["id"] for r in ITEMS if r["slice"] == "test_text"}
    assert tests == {"T1", "T2", "T3", "TN1", "TN2", "TN3"}


# --- Heterographic SemEval split and the evaluation script ------------------

import runpy

EVAL = runpy.run_path(str(CORPUS.parent / "scripts" / "evaluate_soundalike.py"))


def test_semeval_heterographic_split_counts():
    gold = load_gold(CORPUS / "semeval_heterographic_gold.jsonl")
    labels = Counter(g.gold_label.value for g in gold.values())
    assert labels == {"VALID_SOUNDALIKE_JOKE": 1271, "ONE_SENSE_ONLY": 509}
    targets = [json.loads(l) for l in (CORPUS / "semeval_heterographic_targets.jsonl").read_text(encoding="utf-8").splitlines() if l]
    assert len(targets) == 1098 and targets[0] == {"id": "het_1", "pun_word": "alleged", "target_lemmas": ["ledge"]}


def test_shortcut_baselines_are_pinned(capsys):
    EVAL["cmd_baselines"](None)
    out = capsys.readouterr().out
    assert "Always 'pun': P 0.714 | R 1.000 | F1 0.833" in out
    assert "(L1 tokenisation): P 0.824 | R 0.790 | F1 0.807" in out  # design.md reported 0.806
    assert "'Tom' appears in 224 puns and 0 non-puns" in out


def test_binary_similarity_ties_what_graded_ranks():
    from crack.phonetics import sound_similarity
    binary = {pair: round(EVAL["binary_similarity"](*sound_similarity(*pair).pron_pair), 3)
              for pair in [("cat", "cad"), ("pat", "pit"), ("cat", "cash")]}
    assert len(set(binary.values())) == 1  # all 0.667: binary cannot order them


def test_detection_rescoring_counts_items(tmp_path, capsys):
    records = tmp_path / "records.jsonl"
    gold = load_gold(CORPUS / "soundalike_gold.jsonl")
    records.write_text("".join(json.dumps({"item_id": i, "final": {"main_classification": g.gold_label.value}}) + "\n"
                               for i, g in gold.items()), encoding="utf-8")
    import types
    EVAL["cmd_detection"](types.SimpleNamespace(records=str(records), gold=str(CORPUS / "soundalike_gold.jsonl"), all=True))
    out = capsys.readouterr().out
    assert "### Slice: seed" in out and "F1 1.000" in out


@pytest.mark.parametrize("unresolved", ["EXECUTION_FAILED", "INSUFFICIENT_EVIDENCE", "OUT_OF_SCOPE_HOMOPHONE", None])
def test_unresolved_negative_cannot_count_as_correct_or_complete_pair(tmp_path, capsys, unresolved):
    import types
    # S01 and its matched N01 form one pair; a failed or missing negative
    # must stay in the denominator and cannot complete that pair correctly.
    gold = tmp_path / "gold.jsonl"
    gold.write_text(
        json.dumps({"id": "S01", "gold_label": "VALID_SOUNDALIKE_JOKE"}) + "\n" +
        json.dumps({"id": "N01", "gold_label": "ONE_SENSE_ONLY"}) + "\n", encoding="utf-8")
    rows = [{"item_id": "S01", "final": {"main_classification": "VALID_SOUNDALIKE_JOKE"}}]
    if unresolved is not None:
        rows.append({"item_id": "N01", "final": {"main_classification": unresolved}})
    records = tmp_path / "records.jsonl"
    records.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    EVAL["cmd_detection"](types.SimpleNamespace(records=str(records), gold=str(gold), all=True))
    out = capsys.readouterr().out
    assert "### Slice: all (2 items; decided 1/2 (50.0%))" in out
    assert "Binary accuracy (all items; unresolved are incorrect): 1/2 (50.0%)" in out
    assert "TP 1 FP 0 FN 0 TN 0" in out
    assert "Unresolved: 1 (positive 0, negative 1)" in out
    assert "Paired accuracy (a positive and all its negatives right): 0/1 (0.0%)" in out
