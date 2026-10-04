"""Call budgets and terminal states, including the complete production registry."""
import json
import asyncio

import pytest

from crack import age_evidence, l4_anchoring as l4, l5_resolution as l5, l6_distinctness as l6, layers, runner
from crack.config import DEFAULT_SETTINGS
from crack.schema import CandidateEntry, L7Result, L8Result, LayerTrace, SenseEntry
from crack.validation import ModelResponseError
from tests.test_l7 import estimate
from tests.test_response_contract_v3 import payload, record, responses
from tests.test_system_design import anchoring, completed_record, distinctness, fake_l5


def test_unknown_l4_stops_before_another_candidate(monkeypatch):
    rec = record(("crane", "crate"), total=2)
    calls = responses(monkeypatch, [payload(status="INSUFFICIENT_EVIDENCE"), payload("crate")])
    rec.l4_result = l4.anchor_l4(rec)
    assert rec.l4_result.anchoring_status.value == "INSUFFICIENT_EVIDENCE"
    assert len(calls) == 1
    assert rec.l4_search.stop_reason == "INSUFFICIENT_EVIDENCE"


def test_l4_compares_original_top_k_once_without_searching_tail(monkeypatch):
    rec = record(tuple(f"term{i}" for i in range(8)), total=12)
    rec.l3_result.deferred_candidates = [CandidateEntry(term=f"tail{i}", score=.1) for i in range(4)]
    calls = responses(monkeypatch, [payload("term7", "ONE_SENSE_ONLY")])
    result = l4.anchor_l4(rec, DEFAULT_SETTINGS.model_copy(update={"L4_MAX_CANDIDATES": 24}))
    assert len(calls) == 1
    assert rec.l4_search.untested_terms == 11
    assert rec.l4_search.considered_terms == [f"term{i}" for i in range(8)]
    assert "tail0" not in calls[0]
    assert rec.l4_attempts[0].candidate_terms == rec.l4_search.considered_terms
    assert result.anchoring_status.value == "ONE_SENSE_ONLY"


def test_l4_cannot_select_a_candidate_outside_the_offered_budget(monkeypatch):
    rec = record(("crate", "crane"), total=2)
    calls = responses(monkeypatch, [payload(), payload("crate")])
    with pytest.raises(ModelResponseError, match="shortlisted candidate"):
        l4.anchor_l4(rec, DEFAULT_SETTINGS.model_copy(update={"L4_MAX_CANDIDATES": 1}))
    assert len(calls) == 1
    assert rec.l4_search.stop_reason == "EXECUTION_FAILED"
    assert rec.l4_attempts[0].candidate_terms == ["crate"]


def test_empty_extra_key_remains_a_failure_without_correction(monkeypatch):
    rec = record()
    invalid = payload()
    invalid[""] = ""
    calls = responses(monkeypatch, [invalid, payload()])
    with pytest.raises(ModelResponseError, match="unexpected"):
        l4.anchor_l4(rec)
    assert len(calls) == 1
    assert not rec.l4_attempts[0].accepted


@pytest.mark.parametrize("status", ["RESOLUTION_FAIL", "INSUFFICIENT_CONTEXT", "TRUNCATED_OUTPUT"])
def test_l5_nonpass_stops_without_l6_or_new_candidate(monkeypatch, status):
    rec = completed_record()
    rec.l5_result = rec.l5_result.model_copy(update={"resolution_status": status})
    calls = []
    runner.execute_layer("L6", lambda *args: calls.append("L6"), rec,
                         DEFAULT_SETTINGS.model_copy(update={"CONTINUE_AFTER_CANDIDATE_REJECTION": True}))
    assert not calls
    assert rec.l6_result is None
    assert rec.trace[-1].status == "SKIPPED"


@pytest.mark.parametrize("layer", ["L4", "L5", "L6", "L7", "L8"])
def test_failure_discards_partial_results_and_stops_dependent_work(layer):
    rec = completed_record(ages=[8])
    if layer == "L8":
        rec.l7_result = L7Result(per_age_comprehension={8: "FULLY_COMPREHENSIBLE"})
    def broken(record, settings):
        if layer == "L7":
            record.l7_result = L7Result(per_age_comprehension={8: "FULLY_COMPREHENSIBLE"})
        elif layer == "L8":
            record.l8_result = L8Result(per_age_verdict={8: "FULLY_AGE_APPROPRIATE"})
        raise RuntimeError("A stage failed after partially updating its record")
    with pytest.raises(RuntimeError):
        runner.execute_layer(layer, broken, rec, DEFAULT_SETTINGS)
    assert getattr(rec, f"{layer.lower()}_result") is None
    rec.trace.append(LayerTrace(layer=layer, status="ERROR", reason="Controlled failure", duration_ms=1))
    calls = []
    if layer != "L8":
        next_layer = f"L{int(layer[1:]) + 1}"
        runner.execute_layer(next_layer, lambda *args: calls.append(next_layer), rec, DEFAULT_SETTINGS)
        assert not calls
    runner._l0_post_layer(rec, DEFAULT_SETTINGS)
    assert rec.final.detection_status.value == ("PUN" if layer in {"L7", "L8"} else "EXECUTION_FAILED")
    if layer in {"L7", "L8"}:
        assert rec.final.per_age[8].appropriateness.value == "UNKNOWN"


def test_detection_and_age_complete_with_three_model_calls(monkeypatch, tmp_path):
    calls = []
    def retrieve(*args, **kwargs):
        return [SenseEntry(term="crane", lemma="crane", pos="n", sense_id=f"crane.{i}",
                           definition=f"meaning {i}", source="wordnet", lexname=name, semcor_count=1)
                for i, name in enumerate(("noun.animal", "noun.artifact"))]
    monkeypatch.setattr(layers, "retrieve", retrieve)
    def complete_l4(*args):
        calls.append("L4")
        return l4._L4Call(anchoring(), "offline", False, 0)
    monkeypatch.setattr(l4, "_complete_l4", complete_l4)
    fake_l5(monkeypatch)
    original_l5 = l5._complete_json
    def complete_l5(*args, **kwargs):
        calls.append("L5")
        return original_l5(*args, **kwargs)
    monkeypatch.setattr(l5, "_complete_json", complete_l5)
    def complete_l6(prompt, *args):
        calls.append("L6")
        assert '"target_ages": [8]' in prompt
        result = distinctness()
        result.update(ambiguity_ablation="SKIPPED", age_assessment={"8": estimate()})
        return l6._L6Call(result, "offline", False, 0)
    monkeypatch.setattr(l6, "_complete_l6", complete_l6)
    blind = tmp_path / "blind.jsonl"
    blind.write_text(json.dumps({"id": "new", "text": completed_record().text, "target_ages": [8]}) + "\n")
    output = runner.run(blind, DEFAULT_SETTINGS, output_root=tmp_path / "run")
    row = json.loads((output / "records.jsonl").read_text())
    assert calls == ["L4", "L5", "L6"]
    assert row["final"]["detection_status"] == "PUN"
    assert row["final"]["per_age"]["8"] == dict(comprehension="FULLY_COMPREHENSIBLE", appropriateness="FULLY_AGE_APPROPRIATE")
    assert not row["age_attempts"]
    assert all(t["status"] in {"PASS", "OK"} for t in row["trace"])


def test_malformed_age_answer_does_not_change_detection_or_trigger_repair(monkeypatch):
    rec = completed_record(ages=[8])
    rec.l6_result.age_assessment = {"8": {"understanding": "LIKELY"}}
    calls = []
    for name, fn in (("L7", layers.run_l7), ("L8", lambda *args: calls.append("L8"))):
        try:
            runner.execute_layer(name, fn, rec, DEFAULT_SETTINGS)
        except Exception as exc:
            rec.trace.append(LayerTrace(layer=name, status="ERROR", reason=str(exc), duration_ms=1))
    runner._l0_post_layer(rec, DEFAULT_SETTINGS)
    assert calls == []
    assert rec.final.detection_status.value == "PUN"
    assert rec.final.per_age[8].comprehension.value == "AOA_UNKNOWN"
    assert rec.final.per_age[8].appropriateness.value == "UNKNOWN"


def test_age_resource_failure_preserves_detection_task(monkeypatch):
    rec = completed_record(ages=[8])
    def missing(_):
        raise FileNotFoundError("Age evidence resource unavailable")
    monkeypatch.setattr(age_evidence, "age_inputs", missing)
    seen = []
    def complete(prompt, *args):
        seen.append(prompt)
        assert "Set age_assessment to null" in prompt
        return l6._L6Call(distinctness(), "offline", False, 0)
    monkeypatch.setattr(l6, "_complete_l6", complete)
    rec.l6_result = l6.distinctness_l6(rec)
    assert len(seen) == 1
    assert rec.age_preparation_error is not None
    with pytest.raises(ModelResponseError, match="resource unavailable"):
        layers.run_l7(rec, DEFAULT_SETTINGS)
    runner._l0_post_layer(rec, DEFAULT_SETTINGS)
    assert rec.final.detection_status.value == "PUN"


@pytest.mark.parametrize("backend", ["anthropic", "gemini", "openai"])
def test_shared_age_response_survives_real_provider_dispatch(backend):
    from tests.test_l6 import _mock_anthropic_client, _mock_gemini_client, _mock_openai_client
    clients = {"anthropic": _mock_anthropic_client,
               "gemini": _mock_gemini_client, "openai": _mock_openai_client}
    rec = completed_record(ages=[8])
    body = distinctness()
    body["age_assessment"] = {"8": estimate()}
    client = clients[backend](json.dumps(body))
    settings = DEFAULT_SETTINGS.model_copy(update={"L6_BACKEND": backend})
    rec.l6_result = l6.distinctness_l6(rec, settings, client=client)
    layers.run_l7(rec, settings)
    layers.run_l8(rec, settings)
    runner._l0_post_layer(rec, settings)
    assert rec.final.per_age[8].appropriateness.value == "FULLY_AGE_APPROPRIATE"
    call_count = (client.messages.create.call_count if backend == "anthropic" else
                  client.models.generate_content.call_count if backend == "gemini" else
                  client.chat.completions.create.call_count)
    assert call_count == 1


@pytest.mark.parametrize("stream", [False, True])
def test_web_assesses_only_selected_age(monkeypatch, stream):
    from crack import serve
    observed = []
    def execute(name, fn, rec, settings):
        observed.append(list(rec.target_ages))
        if name == "L0-post":
            runner._l0_post_layer(rec, settings)
        return rec
    monkeypatch.setattr(serve, "execute_layer", execute)
    monkeypatch.setattr(serve, "_get_configured_settings", lambda: DEFAULT_SETTINGS)
    async def request():
        if stream:
            response = await serve.stream_analysis(text="The crane nested by the construction crane.", target_age=9)
            events = [event async for event in response.body_iterator]
            return json.loads(next(event.split("data: ", 1)[1] for event in events if event.startswith("event: complete")))
        response = await serve.analyze_joke(serve.AnalyzeRequest(text="The crane nested by the construction crane.", target_age=9))
        return json.loads(response.body)
    result = asyncio.run(request())
    assert observed and all(ages == [9] for ages in observed)
    assert result["target_age"] == 9
    assert result["confidence"] is None
    assert result["detection_status"] == "INSUFFICIENT_EVIDENCE"


def test_age_gold_pun_subset_keeps_missed_puns_in_denominator(tmp_path):
    from crack.corpus import evaluate_run
    gold = [{"id": ident, "gold_label": label, "genre": "DECLARATIVE",
             "ambiguous_term": "crane", "sense_a": "a machine", "sense_b": "a bird",
             "expected_age_verdict": {"8": "FULLY_COMPREHENSIBLE"}}
            for ident, label in [("pun", "VALID_HOMOGRAPH_JOKE"),
                                 ("missed", "VALID_HOMOGRAPH_JOKE"), ("control", "ONE_SENSE_ONLY")]]
    records = [{"item_id": ident, "validation_version": "2", "final": {
        "main_classification": label, "per_age": {"8": {"comprehension": "FULLY_COMPREHENSIBLE"}}}}
        for ident, label in [("pun", "VALID_HOMOGRAPH_JOKE"),
                             ("missed", "INSUFFICIENT_EVIDENCE"), ("control", "ONE_SENSE_ONLY")]]
    gold_path, records_path = tmp_path / "gold.jsonl", tmp_path / "records.jsonl"
    for path, values in [(gold_path, gold), (records_path, records)]:
        path.write_text("\n".join(json.dumps(value) for value in values))
    result = evaluate_run(records_path, gold_path)
    assert result["total_age_evals"] == 3
    assert result["assessed_age_evals"] == 2
    assert result["age_gold_puns"] == dict(total_labels=2, assessed_labels=1, correct_labels=1,
        accuracy_all_labels=.5, assessment_coverage=.5, accuracy_on_assessed=1.0)
