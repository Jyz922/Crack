"""Offline checks for example separation and the prompt-only comparison harness."""

import hashlib
import json
from pathlib import Path
import runpy

import pytest

ROOT = Path(__file__).resolve().parents[1]
audit_module = runpy.run_path(str(ROOT / "scripts/audit_prompt_overlap.py"))
comparison_module = runpy.run_path(str(ROOT / "scripts/compare_prompt_versions.py"))


def test_phrase_audit_normalizes_punctuation_but_preserves_word_boundaries():
    overlap = audit_module["phrase_overlap"]
    phrase = "A violet balloon drifted above the empty station"
    assert overlap(phrase, f'Sample: "{phrase.upper()}!"')[0] == "FAIL"
    assert overlap(phrase, "A violet balloon drifted above the empty stationmaster") == (
        "REVIEW", "a violet balloon drifted above the empty")
    assert overlap("the channel", 'Use "the channel" as input.') is None


def test_current_prompts_and_development_have_no_long_evaluation_matches():
    report = audit_module["audit"](ROOT / "src/crack/prompts", ROOT / "corpus",
                                   ROOT / "corpus/prompt_development/v1/examples.jsonl")
    assert report["failures"] == 0


def test_quoted_shared_word_is_review_hint_not_failure(tmp_path):
    prompts, corpus = tmp_path / "prompts", tmp_path / "corpus"
    prompts.mkdir()
    corpus.mkdir()
    (prompts / "stage.md").write_text('The word “channel” needs contextual evidence.')
    (corpus / "synthetic_blind.jsonl").write_text(json.dumps({"id": "X", "text": "A short new input text."}) + "\n")
    (corpus / "synthetic_gold.jsonl").write_text(json.dumps({"id": "X", "ambiguous_term": "channel"}) + "\n")
    report = audit_module["audit"](prompts, corpus)
    assert report["failures"] == 0
    assert report["findings"][0]["severity"] == "TERM_REVIEW"


def test_development_version_is_frozen_and_families_stay_together():
    folder = ROOT / "corpus/prompt_development/v1"
    manifest = json.loads((folder / "manifest.json").read_text())
    data = (folder / "examples.jsonl").read_bytes()
    assert hashlib.sha256(data).hexdigest() == manifest["examples_sha256"]
    rows = [json.loads(line) for line in data.splitlines()]
    assert len(rows) == len({r["id"] for r in rows}) == manifest["item_count"] == 10
    assert {r["expected_detection"] for r in rows} == {"PUN", "NON_PUN", "INSUFFICIENT_EVIDENCE", "OUT_OF_SCOPE"}
    assert manifest["split"] == "development"
    assert all(row["family_id"] for row in rows)
    for name, expected in manifest["derived_files_sha256"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == expected
    from crack.corpus import load_blind, load_gold
    inputs, gold = load_blind(folder / "blind.jsonl"), load_gold(folder / "expected.jsonl")
    assert {item.id for item in inputs} == gold.keys() == {r["id"] for r in rows}
    assert all(item.target_ages == [] for item in inputs)
    assert all(item.expected_age_verdict == {} for item in gold.values())


def test_snapshots_change_only_prompts_and_reject_configuration_drift(tmp_path):
    from crack.config import DEFAULT_SETTINGS
    module = comparison_module
    before, after = tmp_path / "before", ROOT / "src/crack/prompts"
    before.mkdir()
    for path in after.glob("*.md"):
        (before / path.name).write_bytes(path.read_bytes())
    with (before / "l6_distinctness.md").open("a") as file:
        file.write("\nSynthetic development instruction.\n")
    blind, gold = tmp_path / "blind.jsonl", tmp_path / "gold.jsonl"
    blind.write_text('{"id":"X","text":"An unseen synthetic input.","target_ages":[8]}\n')
    gold.write_text('{"id":"X"}\n')
    output = tmp_path / "comparison"
    manifest = module["prepare"](before, after, output, blind, gold, DEFAULT_SETTINGS, 4, 1)
    assert manifest["changed_prompts"] == ["l6_distinctness.md"]
    assert manifest["gold_sha256"] == hashlib.sha256(gold.read_bytes()).hexdigest()
    for arm in ("before", "after"):
        package = output / "workspaces" / arm / "src/crack"
        assert all(hashlib.sha256((package / name).read_bytes()).hexdigest() == value
                   for name, value in manifest["source_sha256"].items())
        meta = {"blind_sha256": manifest["blind_sha256"], "config": manifest["config"],
                "source_sha256": {**manifest["source_sha256"],
                    **{f"prompts/{name}": value for name, value in manifest["prompt_sha256"][arm].items()}}}
        module["check_run"](meta, manifest, arm)
        meta["config"] = {**meta["config"], "L3_TOP_K": 99}
        with pytest.raises(AssertionError, match="Settings changed"):
            module["check_run"](meta, manifest, arm)
    with pytest.raises(ValueError, match="Output already exists"):
        module["prepare"](before, after, output, blind, gold, DEFAULT_SETTINGS, 4, 1)


def test_prediction_comparison_keeps_unknown_and_failure_states(tmp_path):
    old, new = tmp_path / "old.jsonl", tmp_path / "new.jsonl"
    def row(label):
        return json.dumps({"item_id": "X", "text": "An unseen synthetic input.",
                           "final": {"main_classification": label, "review_reason": "Local reason."}}) + "\n"
    old.write_text(row("EXECUTION_FAILED"))
    new.write_text(row("INSUFFICIENT_EVIDENCE"))
    result = comparison_module["compare_records"](old, new)
    assert result[0]["before"] == "EXECUTION_FAILED"
    assert result[0]["after"] == "INSUFFICIENT_EVIDENCE"


def test_percentage_point_changes_use_counts_not_rounded_percentages():
    def evaluation(correct, decided):
        return {"total_items": 12, "correct_classification": correct, "decided_items": decided,
                "classification_accuracy": round(correct / 12, 4),
                "total_age_evals": 0, "assessed_age_evals": 0, "correct_age_evals": 0,
                "binary_detection": {"correct": correct, "eligible_items": 12, "decided_items": decided,
                                     "tp": 2, "fp": 1, "fn": 1}}
    metrics = comparison_module["metrics"]
    before, after = metrics(evaluation(7, 9)), metrics(evaluation(5, 8))
    assert round((after["classification_accuracy"] - before["classification_accuracy"]) * 100, 2) == -16.67
    assert after["age_accuracy_on_assessed"] is None
