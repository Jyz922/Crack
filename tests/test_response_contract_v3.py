"""Offline failure-path regressions; no benchmark labels or live API calls."""

import json
from concurrent.futures import ThreadPoolExecutor
import warnings

import pytest

from crack.config import DEFAULT_SETTINGS
from crack.corpus import evaluate_run
from crack.decisions import detection_decision
from crack.enums import AnchoringStatus, Genre, ScopeLabel
from crack.l1_surface import analyze
from crack.l2_senses import compound_splits, retrieve
from crack.l3_candidates import rank
from crack import l4_anchoring as l4
from crack.schema import AnalysisRecord, CandidateEntry, L2Result, L3Result, SenseEntry
from crack.validation import ModelResponseError, validate_l4_response

TEXT = "A crane lifted a crate while a crane nested nearby."


def payload(term="crane", status="PASS", **changes):
    p = {
        "target_term": term, "split_parts": [],
        "sense_a": "a lifting machine", "sense_a_anchor_quote": "lifted a crate",
        "sense_b": "a long-legged bird", "sense_b_anchor_quote": "nested nearby",
        "anchor_relation": "separate_contexts", "anchoring_status": status,
        "resolving_sense": "sense_b", "reasoning": "The clauses support different readings.",
    }
    if status != "PASS":
        p.update(anchor_relation=None, resolving_sense=None, sense_b="", sense_b_anchor_quote="")
    p.update(changes)
    return p


def record(terms=("crane",), total=None):
    return AnalysisRecord(
        item_id="synthetic", text=TEXT, target_ages=[8], l1_result=analyze(TEXT),
        l3_result=L3Result(candidates=[CandidateEntry(term=t, score=0.7) for t in terms], total_terms=total),
    )


def responses(monkeypatch, values):
    calls = []
    iterator = iter(values)

    def complete(prompt, settings, client, response_log=None):
        calls.append(prompt)
        p = next(iterator)
        if response_log is not None:
            response_log.append(json.dumps(p))
        return l4._L4Call(p, "offline", False, 0)

    monkeypatch.setattr(l4, "_complete_l4", complete)
    return calls


def test_bad_quote_fails_immediately_and_remains_auditable(monkeypatch):
    r = record()
    bad = payload(sense_a_anchor_quote="Lifted a crate")
    calls = responses(monkeypatch, [bad, payload()])
    with pytest.raises(ModelResponseError, match="verbatim"):
        l4.anchor_l4(r)
    assert len(calls) == 1
    assert len(r.l4_attempts) == 1 and not r.l4_attempts[0].accepted
    assert r.l4_attempts[0].parsed_response == bad
    assert json.loads(r.l4_attempts[0].raw_responses[0]) == bad


def test_target_drift_is_rejected_without_repair_or_another_candidate(monkeypatch):
    r = record()
    bad = payload(target_term="crate", reasoning="crane appears in this explanation")
    calls = responses(monkeypatch, [bad, payload()])
    with pytest.raises(ModelResponseError, match="target_term"):
        l4.anchor_l4(r)
    assert len(calls) == 1
    assert not any(a.accepted for a in r.l4_attempts)
    assert r.l4_attempts[0].parsed_response["target_term"] == "crate"


def test_completion_failure_is_logged_without_contract_retry(monkeypatch):
    calls = []
    r = record()

    def truncated(prompt, settings, client, response_log=None):
        calls.append(prompt)
        response_log.append('{"target_term":')
        raise ModelResponseError("Model response did not complete normally: length")

    monkeypatch.setattr(l4, "_complete_l4", truncated)
    with pytest.raises(ModelResponseError, match="length"):
        l4.anchor_l4(r)
    assert len(calls) == 1
    assert r.l4_attempts[0].raw_responses == ['{"target_term":']
    assert not r.l4_attempts[0].accepted


def test_uncertainty_is_accepted_without_retrying_until_pass(monkeypatch):
    r = record()
    calls = responses(monkeypatch, [payload(status="INSUFFICIENT_EVIDENCE")])
    assert l4.anchor_l4(r).anchoring_status == AnchoringStatus.INSUFFICIENT_EVIDENCE
    assert len(calls) == 1


def test_later_candidate_pass_is_used_and_rotated(monkeypatch):
    r = record(("crate", "crane"), total=2)
    calls = responses(monkeypatch, [payload()])
    result = l4.anchor_l4(r)
    assert result.target_term == "crane"
    assert r.l3_result.candidates[0].term == "crane"
    assert [a.candidate_term for a in r.l4_attempts] == ["crane"]
    assert len(calls) == 1
    assert r.l4_attempts[0].candidate_terms == ["crate", "crane"]


def test_selected_uncertain_candidate_remains_aligned(monkeypatch):
    r = record(("crate", "crane"), total=2)
    responses(monkeypatch, [payload(status="INSUFFICIENT_EVIDENCE")])
    r.l4_result = l4.anchor_l4(r)
    assert r.l3_result.candidates[0].term == r.l4_result.target_term == "crane"
    assert detection_decision(r, ScopeLabel.HOMOGRAPH)[0].value == "INSUFFICIENT_EVIDENCE"


def test_explicit_candidate_remains_aligned(monkeypatch):
    r = record(("crate", "crane"), total=2)
    responses(monkeypatch, [payload()])
    r.l4_result = l4.anchor_l4(r, ambiguous_term="crane")
    assert r.l3_result.candidates[0].term == r.l4_result.target_term == "crane"
    with pytest.raises(ValueError, match="supplied L3 candidates"):
        l4.anchor_l4(r, ambiguous_term="nearby")


def test_selected_candidate_survives_final_decision_and_serialization(monkeypatch):
    from crack.runner import _l0_post_layer
    from crack.schema import L5DeclarativeResult, L6Result
    from crack.validation import RESPONSE_CONTRACT_VERSION

    r = record(("crate", "crane"), total=2)
    r.validation_version = RESPONSE_CONTRACT_VERSION
    responses(monkeypatch, [payload()])
    r.l4_result = l4.anchor_l4(r)
    r.l5_result = L5DeclarativeResult(
        genre=Genre.DECLARATIVE, resolution_status="RESOLUTION_PASS", resolution_score=0.9,
        context_consistent=True,
        subscores={"both_readings_available": 0.9, "punchline_sense_is_unexpected": 0.9,
                   "incongruity_present": 0.9}, explanation="Synthetic completed assessment.",
    )
    r.l6_result = L6Result(
        distinctness_status="SENSES_DISTINCT", ambiguity_ablation="SUPPORTED",
        sense_a_paraphrase="A machine lifted a crate.", sense_b_paraphrase="A bird nested nearby.",
        suppresses_other=True, materially_different=True, explanation="Synthetic rewrite assessment.",
    )
    _l0_post_layer(r, DEFAULT_SETTINGS)
    restored = AnalysisRecord.model_validate_json(r.model_dump_json())
    assert restored.final.main_classification.value == "VALID_HOMOGRAPH_JOKE"
    assert detection_decision(restored, restored.final.scope_label)[0] == restored.final.main_classification
    assert restored.l3_result.candidates[0].term == restored.l4_result.target_term == "crane"
    assert [a.accepted for a in restored.l4_attempts] == [True]


def test_run_fingerprint_records_sources_and_excludes_secrets(tmp_path):
    from crack.runner import _run_fingerprint

    blind = tmp_path / "blind.jsonl"
    blind.write_text('{"id":"unseen","text":"A short sentence.","target_ages":[8]}\n')
    settings = DEFAULT_SETTINGS.model_copy(update={
        "OPENAI_API_KEY": "private-test-value", "OPENAI_BASE_URL": "https://private.invalid", "L3_TOP_K": 6,
    })
    frozen = _run_fingerprint(blind, settings)
    assert frozen["config"]["L3_TOP_K"] == 6
    assert len(frozen["blind_sha256"]) == 64
    assert len(frozen["source_sha256"]["prompts/l4_anchoring.md"]) == 64
    assert len(frozen["source_sha256"]["l4_anchoring.py"]) == 64
    assert "private-test-value" not in json.dumps(frozen)
    assert "private.invalid" not in json.dumps(frozen)
    assert _run_fingerprint(blind, settings) == frozen


def test_shortlist_rejection_does_not_force_an_exhaustive_search(monkeypatch):
    r = record(total=3)
    calls = responses(monkeypatch, [payload(status="ONE_SENSE_ONLY")])
    r.l4_result = l4.anchor_l4(r)
    assert r.l4_result.anchoring_status == AnchoringStatus.ONE_SENSE_ONLY
    assert r.l4_search.untested_terms == 2
    assert detection_decision(r, ScopeLabel.HOMOGRAPH)[0].value == "ONE_SENSE_ONLY"
    assert len(calls) == 1


def test_complete_supplied_search_can_return_negative(monkeypatch):
    r = record(total=1)
    responses(monkeypatch, [payload(status="ONE_SENSE_ONLY")])
    assert l4.anchor_l4(r).anchoring_status == AnchoringStatus.ONE_SENSE_ONLY


def test_no_candidate_does_not_guess_first_word_or_call_model(monkeypatch):
    r = record((), total=0)
    calls = responses(monkeypatch, [])
    r.l4_result = l4.anchor_l4(r)
    assert r.l4_result.anchoring_status == AnchoringStatus.INSUFFICIENT_EVIDENCE
    assert detection_decision(r, ScopeLabel.NO_SCOPE_MECHANISM)[0].value == "INSUFFICIENT_EVIDENCE"
    assert not calls


def sense(term, ident, lexname, count=0, source="wordnet", lemma=None):
    return SenseEntry(term=term, lemma=lemma or term, pos="n", sense_id=ident,
                      definition=ident, source=source, lexname=lexname, semcor_count=count)


def test_unobserved_frequency_is_visible_and_does_not_exclude_a_sense():
    senses = [sense("unseen", "u.a", "noun.object"), sense("unseen", "u.b", "noun.animal"),
              sense("observed", "o.a", "noun.object", 10), sense("observed", "o.b", "noun.animal", 10)]
    cands = rank(senses, 2).candidates
    assert {c.term for c in cands} == {"observed", "unseen"}
    assert cands[1].score_components["balance_observed"] == 0
    assert cands[1].score_components["contrast"] == 1
    assert all(0 <= c.score <= 1 for c in cands)


def test_higher_ranked_homograph_does_not_erase_split_options():
    senses = [sense("overcoat", "whole.a", "noun.artifact", 10),
              sense("overcoat", "whole.b", "verb.change", 10),
              sense("overcoat", "part.a", "noun.quantity", 0, "wordnet_split:over+coat", "over"),
              sense("overcoat", "part.b", "noun.artifact", 80, "wordnet_split:over+coat", "coat")]
    result = rank(senses, 1)
    assert result.total_terms == 1
    c = result.candidates[0]
    assert c.sense_a_id == "whole.a"
    assert c.split_options == [("over", "coat")]
    assert c.score_components["compound_split"] == 1


def test_all_senses_are_visible_and_split_is_optional(monkeypatch):
    r = record(("crane",), total=1)
    r.l3_result.candidates[0].split_options = [("cr", "ane")]
    r.l3_result.candidates[0].score_components["compound_split"] = 1
    r.l2_result = L2Result(senses=[sense("crane", f"sense.{i}", "noun.object") for i in range(7)])
    calls = responses(monkeypatch, [payload()])
    result = l4.anchor_l4(r)
    assert "sense.6" in calls[0]
    assert '["cr", "ane"]' in calls[0]
    assert result.anchor_relation.value == "separate_contexts"
    assert result.split_parts == []


def test_only_supplied_split_can_pass():
    text = "Cupboard: a board to hold a cup."
    p = payload("cupboard", sense_a_anchor_quote="Cupboard", sense_b_anchor_quote="Cupboard",
                anchor_relation="resegmentation", split_parts=["cup", "board"])
    validate_l4_response(p, text, "cupboard", True, [("cup", "board")])
    with pytest.raises(ModelResponseError, match="supplied segmentation"):
        validate_l4_response(p, text, "cupboard", True, [("cu", "pboard")])


def test_short_parts_are_dictionary_proposals_not_prefix_allowlist():
    assert ("up", "on") in compound_splits("upon")
    assert compound_splits("upon", min_part=3) == []
    assert all(len(a) >= 2 and len(b) >= 2 and a + b == "upon" for a, b in compound_splits("upon"))


def test_concurrent_lexical_reads_match_serial_without_offset_warnings():
    words = ["crane", "seal", "coach", "draft", "pitch", "watch", "club", "scale", "jam", "light"]
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        with ThreadPoolExecutor(max_workers=4) as pool:
            concurrent = list(pool.map(lambda w: retrieve([w]), words))
    assert not any("No WordNet synset" in str(w.message) for w in seen)
    for word, entries in zip(words, concurrent):
        assert entries == retrieve([word])


def test_age_coverage_distinguishes_skipped_from_assessed(tmp_path):
    gold = []
    for ident in ("unseen_a", "unseen_b"):
        gold.append({"id": ident, "gold_label": "ONE_SENSE_ONLY", "genre": "DECLARATIVE",
                     "ambiguous_term": "term", "sense_a": "one", "sense_b": "",
                     "expected_age_verdict": {"6": "FULLY_COMPREHENSIBLE", "8": "FULLY_COMPREHENSIBLE", "10": "FULLY_COMPREHENSIBLE"}})
    records = [{"item_id": "unseen_a", "validation_version": "2", "final": {
        "main_classification": "ONE_SENSE_ONLY", "per_age": {
            "6": {"comprehension": "PARTIALLY_COMPREHENSIBLE"},
            "8": {"comprehension": "FULLY_COMPREHENSIBLE"},
            "10": {"comprehension": "AOA_UNKNOWN"}}}},
        {"item_id": "unseen_b", "validation_version": "2", "final": {"main_classification": "ONE_SENSE_ONLY", "per_age": {}}}]
    gold_path, record_path = tmp_path / "gold.jsonl", tmp_path / "records.jsonl"
    gold_path.write_text("\n".join(json.dumps(g) for g in gold))
    record_path.write_text("\n".join(json.dumps(r) for r in records))
    result = evaluate_run(record_path, gold_path)
    assert result["total_age_evals"] == 6
    assert result["assessed_age_evals"] == 2
    assert result["age_accuracy_on_assessed"] == 0.5
    assert result["age_assessment_coverage"] == 0.3333
    assert result["age_accuracy"] == 0.1667
