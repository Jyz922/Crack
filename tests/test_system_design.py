"""Offline design regressions using synthetic inputs and model responses.

These check execution/acceptance rules, not model accuracy on the project corpus.
"""

import json
import socket
import threading
import time
from unittest.mock import MagicMock

import pytest

from crack import l2_senses as l2, l4_anchoring as l4, l5_resolution as l5
from crack import l6_distinctness as l6, layers, runner
from crack.config import DEFAULT_SETTINGS
from crack.decisions import detection_decision
from crack.enums import AmbiguityAblation, Genre, ResolutionStatus, ScopeLabel
from crack.l1_surface import analyze
from crack.schema import (
    AnalysisRecord, CandidateEntry, L3Result, L4Result, L5DeclarativeResult,
    L6Result, LayerTrace, SenseEntry,
)
from crack.validation import (
    RESPONSE_CONTRACT_VERSION, ModelResponseError, validate_l5_response,
    validate_l6_response,
)

TEXT = "A crane lifted a crate while a crane nested nearby."


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Design regressions must not access the network")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


def anchoring():
    return dict(
        target_term="crane", split_parts=[],
        sense_a="a lifting machine", sense_a_anchor_quote="lifted a crate",
        sense_b="a long-legged bird", sense_b_anchor_quote="nested nearby",
        anchor_relation="separate_contexts", anchoring_status="PASS",
        resolving_sense="sense_b", reasoning="The two clauses support different readings.",
    )


def distinctness(**changes):
    return dict(
        sense_a_paraphrase="a machine for lifting loads",
        sense_b_paraphrase="a long-legged nesting bird",
        suppresses_other=False, materially_different=True,
        distinctness_status="SENSES_DISTINCT", ambiguity_ablation="SUPPORTED",
        explanation="Replacing each crane with its single-sense description removes the shared-spelling contrast.",
        **changes,
    )


def record(text=TEXT, genre=None, ages=None):
    if genre == Genre.QA_RIDDLE and text == TEXT:
        text = "Why had a crane lifted a crate? A crane nested nearby."
    rec = AnalysisRecord(
        item_id="synthetic", text=text, target_ages=ages or [],
        validation_version=RESPONSE_CONTRACT_VERSION,
        l1_result=analyze(text),
        l3_result=L3Result(candidates=[CandidateEntry(term="crane", score=.9)], total_terms=1),
        l4_result=L4Result(**anchoring()),
    )
    if genre is not None:
        rec.l1_result.genre = genre
    return rec


def completed_record(**changes):
    rec = record(**changes)
    rec.l5_result = L5DeclarativeResult(
        genre=Genre.DECLARATIVE, resolution_status="RESOLUTION_PASS",
        context_consistent=True, resolution_score=.9,
        subscores={k: .9 for k in l5._L5_DECLARATIVE_WEIGHTS},
        explanation="The text juxtaposes two conventional readings.",
    )
    rec.l6_result = L6Result(**distinctness())
    return rec


def fake_l5(monkeypatch, *, sufficient=True, consistent=True, overrides=None):
    seen = []
    def complete(prompt, required_keys, response_model, settings, client, diagnostics=None):
        seen.append((prompt, response_model))
        scores = required_keys - {"evidence_sufficient", "context_consistent", "reasoning"}
        payload = {k: .9 if sufficient else None for k in scores}
        payload.update(
            evidence_sufficient=sufficient,
            context_consistent=consistent if sufficient else None,
            reasoning="The supplied wording supports the contrast." if sufficient
            else "The referent needed to interpret the contrast was omitted.",
        )
        payload.update(overrides or {})
        return l5._L5Call(payload, "offline", False, 0)
    monkeypatch.setattr(l5, "_complete_json", complete)
    return seen


@pytest.mark.parametrize("genre", list(Genre))
def test_each_l5_form_can_pass_with_complete_supported_response(monkeypatch, genre):
    fake_l5(monkeypatch)
    result = l5.resolve_l5(record(genre=genre), DEFAULT_SETTINGS)
    assert result.resolution_status.value == "RESOLUTION_PASS"
    assert result.context_consistent is True


def test_self_contained_question_uses_general_branch(monkeypatch):
    calls = fake_l5(monkeypatch)
    rec = record(text="Why did a crane lift a crate while a crane nested nearby?")
    assert rec.l1_result.genre == Genre.QA_RIDDLE
    result = l5.resolve_l5(rec, DEFAULT_SETTINGS)
    assert result.genre == Genre.DECLARATIVE
    assert result.resolution_status.value == "RESOLUTION_PASS"
    assert calls[0][1] is l5._DeclarativeLLMResponse
    assert "self-contained question" in calls[0][0]


def test_question_with_answer_keeps_qa_branch(monkeypatch):
    calls = fake_l5(monkeypatch)
    rec = record(text="Why did a crane lift a crate? Another crane nested nearby.")
    assert l5.resolve_l5(rec, DEFAULT_SETTINGS).genre == Genre.QA_RIDDLE
    assert calls[0][1] is l5._QALLMResponse


@pytest.mark.parametrize("genre", list(Genre))
def test_explicit_conflict_cannot_be_averaged_into_pass(monkeypatch, genre):
    fake_l5(monkeypatch, consistent=False)
    result = l5.resolve_l5(record(genre=genre), DEFAULT_SETTINGS)
    assert result.resolution_score == .9
    assert result.resolution_status.value == "RESOLUTION_FAIL"
    assert result.context_consistent is False


def test_absent_optional_qa_features_are_not_contract_failure(monkeypatch):
    fake_l5(monkeypatch, overrides={"causal": 0, "agent": 0, "tense_aspect": 0})
    result = l5.resolve_l5(record(genre=Genre.QA_RIDDLE), DEFAULT_SETTINGS)
    assert result.resolution_status.value == "RESOLUTION_PASS"
    assert result.resolution_score == .63


def test_insufficient_context_stays_unknown_not_negative(monkeypatch):
    fake_l5(monkeypatch, sufficient=False)
    rec = record()
    rec.l5_result = l5.resolve_l5(rec, DEFAULT_SETTINGS)
    assert rec.l5_result.context_consistent is None
    assert rec.l5_result.resolution_score is None
    assert detection_decision(rec, ScopeLabel.HOMOGRAPH)[0].value == "INSUFFICIENT_EVIDENCE"


@pytest.mark.parametrize("suppression", [True, False, None])
def test_distinct_readings_need_not_exclude_each_other(monkeypatch, suppression):
    payload = distinctness()
    payload["suppresses_other"] = suppression
    monkeypatch.setattr(l6, "_complete_l6", lambda *a: l6._L6Call(payload, "offline", False, 0))
    rec = completed_record()
    rec.l6_result = l6.distinctness_l6(rec)
    assert detection_decision(rec, ScopeLabel.HOMOGRAPH)[0].value == "VALID_HOMOGRAPH_JOKE"


@pytest.mark.parametrize("change", [
    {"materially_different": False},
    {"sense_b_paraphrase": "a machine for lifting loads"},
    {"suppresses_other": "false"},
])
def test_relaxed_suppression_still_rejects_inconsistent_evidence(change):
    payload = distinctness()
    payload.update(change)
    with pytest.raises(ModelResponseError):
        validate_l6_response(payload)


def test_ablation_is_a_diagnostic_and_does_not_override_distinct_readings():
    rec = completed_record()
    for diagnostic in (AmbiguityAblation.UNSUPPORTED, AmbiguityAblation.SKIPPED):
        rec.l6_result.ambiguity_ablation = diagnostic
        assert detection_decision(rec, ScopeLabel.HOMOGRAPH)[0].value == "VALID_HOMOGRAPH_JOKE"


@pytest.mark.parametrize("change", [
    {"context_consistent": None}, {"context_consistent": "true"},
    {"both_readings_available": float("nan")}, {"both_readings_available": True},
    {"evidence_sufficient": False},
])
def test_l5_malformed_evidence_is_never_filled_into_pass(change):
    payload = {k: .9 for k in l5._L5_DECLARATIVE_WEIGHTS}
    payload.update(evidence_sufficient=True, context_consistent=True, reasoning="Source-based reasoning.")
    payload.update(change)
    with pytest.raises(ModelResponseError):
        validate_l5_response(payload, set(l5._L5_DECLARATIVE_WEIGHTS))


def test_saved_current_positive_cannot_contradict_context_flag():
    rec = completed_record()
    rec.l5_result = rec.l5_result.model_copy(update={"context_consistent": False})
    assert detection_decision(rec, ScopeLabel.HOMOGRAPH)[0].value == "EXECUTION_FAILED"


@pytest.mark.parametrize("text,expected", [
    ("Liquid assets rose.", True), ("Liquid. Assets rose.", False),
])
def test_mwe_candidates_must_occur_in_source(monkeypatch, text, expected):
    calls = []
    monkeypatch.setattr(l2, "mwe_spans", lambda t: [("Liquid assets", "liquid_assets")])
    monkeypatch.setattr(l2, "compound_splits", lambda t: [])
    def senses(key, **kwargs):
        calls.append((key, kwargs))
        return []
    monkeypatch.setattr(l2, "senses_for", senses)
    l2.retrieve(analyze(text).tokens, text=text)
    assert any(k == "liquid_assets" for k, kw in calls) is expected


def test_no_requested_ages_skip_age_calls():
    rec = completed_record()
    def forbidden(*args):
        pytest.fail("No age assessment should run without requested ages")
    for name in ("L7", "L8"):
        runner.execute_layer(name, forbidden, rec, DEFAULT_SETTINGS)
    assert all(t.status == "SKIPPED" for t in rec.trace)
    runner._l0_post_layer(rec, DEFAULT_SETTINGS)
    assert rec.final.detection_status.value == "PUN"


def test_age_failure_preserves_detection_without_default_age_pass():
    from crack.serve import _build_final_payload
    rec = completed_record(ages=[8])
    rec.trace.append(LayerTrace(layer="L7", status="ERROR", reason="Offline simulated timeout", duration_ms=1))
    runner._l0_post_layer(rec, DEFAULT_SETTINGS)
    assert rec.final.detection_status.value == "PUN"
    assert rec.final.per_age[8].comprehension.value == "AOA_UNKNOWN"
    payload = _build_final_payload(rec, 8)
    assert payload["punchline"] == "crane"
    assert payload["safety"]["is_safe"] is None


def test_incidental_soundalikes_do_not_override_homograph_evidence():
    rec = completed_record(text=TEXT + " A knight arrived at night.")
    runner._l0_post_layer(rec, DEFAULT_SETTINGS)
    assert rec.final.scope_label == ScopeLabel.HOMOGRAPH
    assert rec.final.detection_status.value == "PUN"


def test_frontend_hides_unconfirmed_readings():
    from crack.serve import _build_final_payload
    rec = completed_record(ages=[8])
    rec.l5_result = rec.l5_result.model_copy(update={"resolution_status": ResolutionStatus.RESOLUTION_FAIL})
    runner._l0_post_layer(rec, DEFAULT_SETTINGS)
    payload = _build_final_payload(rec, 8)
    assert payload["detection_status"] == "NON_PUN"
    assert payload["punchline"] is payload["sense_a"] is payload["sense_b"] is None
    assert not payload["age_assessment_available"]


def test_braced_user_data_is_not_rendered_as_template_fields():
    rec = record(text=TEXT + " {sense_a} {term}")
    p5 = l5._render_prompt(Genre.DECLARATIVE, rec.text, "crane", rec.l4_result)
    p6 = l6._render_l6_prompt(rec.text, Genre.DECLARATIVE, "crane", "A", "", "B", "")
    assert rec.text in p5 and rec.text in p6
    assert 'Sense A context anchor: ""' in p6


def test_resume_allows_added_items_but_requires_same_source_and_settings(tmp_path):
    records = tmp_path / "records.jsonl"
    records.write_text("")
    fingerprint = {"source_sha256": {"a.py": "frozen"}, "config": {"L5_MODEL": "fixed"}, "blind_sha256": "new"}
    (tmp_path / "run_meta.json").write_text(json.dumps({**fingerprint, "blind_sha256": "old"}))
    runner._check_resume_fingerprint(records, fingerprint)


def age_payload():
    from crack.age_evidence import AOA_SOURCE
    table = [{"word": "crane", "aoa": 4.0, "match": "exact", "source": AOA_SOURCE},
             {"word": "crate", "aoa": None, "match": "miss", "source": AOA_SOURCE}]
    return {"target_ages": [8], "mandatory_vocabulary": ["crane"], "aoa_lookup": table}


def age_response(**dimensions):
    from crack.l7_comprehension import DIMENSIONS
    return {"required_vocabulary": ["crane", "crate"],
            "aoa_evidence": age_payload()["aoa_lookup"],
            "per_age_details": {"8": {**{d: "LIKELY" for d in DIMENSIONS}, **dimensions,
                "prerequisites": [], "reason": "The word rating supports familiarity; the unrated vocabulary and reading judgments are contextual estimates."}},
            "explanation": "An age-specific estimate with the supplied word-level citations."}


def test_unrated_vocabulary_does_not_automatically_block_age_estimate():
    from crack.l7_comprehension import validate_l7
    result = validate_l7(age_response(), age_payload())
    assert result.aoa_evidence[1].aoa is None
    assert result.per_age_comprehension[8].value == "FULLY_COMPREHENSIBLE"
    assert result.sense_a_aoa is result.sense_b_aoa is result.metalinguistic_floor is None


def test_known_age_barrier_and_unknown_are_both_preserved():
    from crack.l7_comprehension import validate_l7
    result = validate_l7(age_response(sense_b="UNLIKELY", background_knowledge="UNKNOWN"), age_payload())
    summary = result.per_age_summaries[8]
    assert summary.barrier_dimensions == ["sense_b"]
    assert summary.unknown_dimensions == ["background_knowledge"]
    assert not summary.fully_assessed
    assert summary.status.value == "SENSE_B_TOO_ADVANCED"


def test_age_citation_cannot_invent_a_missing_rating():
    from crack.l7_comprehension import validate_l7
    response = age_response()
    response["aoa_evidence"][1]["aoa"] = 5.0
    with pytest.raises(ModelResponseError, match="exactly match"):
        validate_l7(response, age_payload())


@pytest.mark.parametrize("axis", ["content_appropriate", "inference_appropriate"])
def test_age_rejection_needs_its_own_evidence(axis):
    from crack.l7_comprehension import validate_l7
    from crack.l8_appropriateness import validate_l8
    rec = completed_record(ages=[8])
    rec.l7_result = validate_l7(age_response(), age_payload())
    response = {"content_appropriate": {"8": True}, "inference_appropriate": {"8": True},
                "per_age_reasons": {"8": "A contextual estimate for both axes."},
                "content_evidence": [], "inference_issues": [], "explanation": "Age assessment."}
    response[axis]["8"] = False
    with pytest.raises(ModelResponseError, match="rejection requires"):
        validate_l8(response, age_payload(), rec)


def test_null_age_axis_does_not_become_default_approval():
    from crack.l7_comprehension import validate_l7
    from crack.l8_appropriateness import validate_l8
    rec = completed_record(ages=[8])
    rec.l7_result = validate_l7(age_response(), age_payload())
    response = {"content_appropriate": {"8": True}, "inference_appropriate": {"8": None},
                "per_age_reasons": {"8": "Content is ordinary; the inference basis is unavailable."},
                "content_evidence": [], "inference_issues": [], "explanation": "One axis is unknown."}
    assert validate_l8(response, age_payload(), rec).per_age_verdict[8].value == "UNKNOWN"


def test_standalone_age_calls_are_disabled():
    from crack.age_evidence import call_age_model
    client = MagicMock()
    with pytest.raises(ModelResponseError, match="Standalone age calls are disabled"):
        call_age_model(completed_record(ages=[8]), DEFAULT_SETTINGS, "L7", {}, lambda p: p, client)
    client.chat.completions.create.assert_not_called()
    client.messages.create.assert_not_called()
    client.models.generate_content.assert_not_called()


@pytest.mark.parametrize("kind", ["missing", "source", "config", "malformed"])
def test_incompatible_resume_is_rejected_before_calls(tmp_path, kind, monkeypatch):
    blind = tmp_path / "blind.jsonl"
    blind.write_text(json.dumps({"id": "X", "text": TEXT, "target_ages": []}) + "\n")
    cache = tmp_path / "records.jsonl"
    cache.write_text("")
    frozen = runner._run_fingerprint(blind, DEFAULT_SETTINGS)
    if kind in {"source", "config"}:
        frozen["source_sha256" if kind == "source" else "config"] = {}
        (tmp_path / "run_meta.json").write_text(json.dumps(frozen))
    elif kind == "malformed":
        (tmp_path / "run_meta.json").write_text("[]")
    monkeypatch.setattr(runner, "_LAYER_REGISTRY", [("L4", lambda *a: pytest.fail("No call before resume validation"))])
    with pytest.raises(ValueError, match="Resume"):
        runner.run(blind, DEFAULT_SETTINGS.model_copy(), tmp_path / "output", cache)


@pytest.mark.parametrize("mode,expected", [
    ("positive", "PUN"), ("negative", "NON_PUN"),
    ("unknown", "INSUFFICIENT_EVIDENCE"), ("malformed", "EXECUTION_FAILED"),
])
def test_whole_detection_path_keeps_four_outcomes_separate(monkeypatch, tmp_path, mode, expected):
    from crack.corpus import evaluate_run
    blind, gold = tmp_path / "blind.jsonl", tmp_path / "gold.jsonl"
    blind.write_text(json.dumps({"id": "synthetic", "text": TEXT, "target_ages": []}) + "\n")
    gold.write_text(json.dumps({"id": "synthetic", "gold_label": "VALID_HOMOGRAPH_JOKE",
        "genre": "DECLARATIVE", "ambiguous_term": "crane", "sense_a": "machine", "sense_b": "bird",
        "expected_age_verdict": {}}) + "\n")
    senses = [SenseEntry(term="crane", lemma="crane", pos="n", sense_id=f"synthetic.{i}",
                        definition=d, source="wordnet", lexname=ln, semcor_count=1)
              for i, d, ln in [(1, "machine", "noun.artifact"), (2, "bird", "noun.animal")]]
    monkeypatch.setattr(layers, "retrieve", lambda *a, **kw: senses)
    monkeypatch.setattr(l4, "_complete_l4", lambda *a, **kw: l4._L4Call(anchoring(), "offline", False, 0))
    fake_l5(monkeypatch, sufficient=mode != "unknown", consistent=mode != "negative",
            overrides={"context_consistent": "true"} if mode == "malformed" else None)
    monkeypatch.setattr(l6, "_complete_l6", lambda *a: l6._L6Call(distinctness(), "offline", False, 0))
    output = runner.run(blind, DEFAULT_SETTINGS.model_copy(), tmp_path / "output")
    rec = AnalysisRecord.model_validate_json((output / "records.jsonl").read_text().strip())
    assert rec.final.detection_status.value == expected
    report = evaluate_run(output / "records.jsonl", gold)
    assert report["outcome_counts"][expected] == 1
    assert report["unverified_contract_items"] == 0
    assert report["decided_items"] == int(mode in {"positive", "negative"})
    assert report["correct_classification"] == int(mode == "positive")
    if mode in {"unknown", "malformed"}:
        assert report["binary_detection"]["tn"] == report["binary_detection"]["fn"] == 0
        assert report["binary_detection"]["abstentions_by_gold_class"]["positive"] == 1


def test_sixty_synthetic_items_complete_concurrently_and_resume(monkeypatch, tmp_path):
    """A capacity/contract regression, not a measured 60-item corpus score."""
    blind = tmp_path / "blind.jsonl"
    blind.write_text("".join(json.dumps({"id": f"synthetic_{i}", "text": TEXT + f" Item {i}.", "target_ages": []}) + "\n" for i in range(60)))
    senses = [SenseEntry(term="crane", lemma="crane", pos="n", sense_id=f"synthetic.{i}",
                        definition=d, source="wordnet", lexname=ln, semcor_count=1)
              for i, d, ln in [(1, "a lifting machine", "noun.artifact"), (2, "a nesting bird", "noun.animal")]]
    monkeypatch.setattr(layers, "retrieve", lambda *a, **kw: senses)
    lock = threading.Lock()
    active = peak = calls = 0
    def complete(prompt, settings, client, response_log=None):
        nonlocal active, peak, calls
        with lock:
            active += 1
            calls += 1
            peak = max(peak, active)
        time.sleep(.01)
        with lock:
            active -= 1
        return l4._L4Call(anchoring(), "offline", False, 0)
    monkeypatch.setattr(l4, "_complete_l4", complete)
    fake_l5(monkeypatch)
    monkeypatch.setattr(l6, "_complete_l6", lambda *a: l6._L6Call(distinctness(), "offline", False, 0))
    settings = DEFAULT_SETTINGS.model_copy()
    output = runner.run(blind, settings, tmp_path / "batch", concurrency=8)
    records = [AnalysisRecord.model_validate_json(line) for line in (output / "records.jsonl").read_text().splitlines()]
    assert len(records) == len({r.item_id for r in records}) == 60
    assert all(r.final.detection_status.value == "PUN" for r in records)
    assert not any(t.status == "ERROR" for r in records for t in r.trace)
    assert 2 <= peak <= 8 and calls == 60
    resumed = runner.run(blind, settings, tmp_path / "resumed", output / "records.jsonl", concurrency=8)
    assert len((resumed / "records.jsonl").read_text().splitlines()) == 60
    assert calls == 60
