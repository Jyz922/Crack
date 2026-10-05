"""Web boundary regressions: real execution guards, offline provider responses."""
from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from crack import age_evidence, l4_anchoring as l4, l5_resolution as l5
from crack import l6_distinctness as l6, l7_comprehension as l7, layers, runner, serve
from crack.config import DEFAULT_SETTINGS
from crack.schema import L3Result, SenseEntry
from tests.test_l7 import estimate
from tests.test_response_contract_v3 import payload as anchor_payload
from tests.test_system_design import TEXT, distinctness, fake_l5


def prepare_pipeline(monkeypatch, case="pass"):
    """Run the production registry while replacing only its external dependencies."""
    calls = []
    recovered = case in {"recovery", "recovery-invalid"}
    monkeypatch.setattr(serve, "_get_configured_settings", lambda: DEFAULT_SETTINGS)
    monkeypatch.setattr(age_evidence, "aoa_lookup", lambda word: (4.0, "exact"))
    monkeypatch.setattr(l7, "resource_sha256", lambda: "a" * 64)
    monkeypatch.setattr(layers, "retrieve", lambda *a, **kw: [
        SenseEntry(term="crane", lemma="crane", pos="n", sense_id=f"crane.{i}",
                   definition=f"meaning {i}", source="wordnet", lexname=lexname, semcor_count=1)
        for i, lexname in enumerate(("noun.animal", "noun.artifact"))
    ])
    if case == "L2-unknown":
        monkeypatch.setattr(layers, "retrieve", lambda *a, **kw: [])
    if case == "L3-unknown":
        monkeypatch.setattr(layers, "rank", lambda *a, **kw: L3Result())

    def complete_l4(*args):
        calls.append("L4")
        status = {"L4-unknown": "INSUFFICIENT_EVIDENCE", "L4-negative": "ONE_SENSE_ONLY"}.get(case, "PASS")
        body = anchor_payload(status=status)
        if case == "resolve-a":
            body["resolving_sense"] = "sense_a"
        return l4._L4Call(body, "offline-fallback" if recovered else "offline", recovered, 3 if recovered else 0)
    monkeypatch.setattr(l4, "_complete_l4", complete_l4)
    fake_l5(monkeypatch, sufficient=case != "L5-unknown",
            overrides={"context_consistent": False} if case == "L5-negative" else None)
    original_l5 = l5._complete_json
    def complete_l5(*args, **kwargs):
        calls.append("L5")
        result = original_l5(*args, **kwargs)
        if case == "L5-truncated":
            return l5._L5Call(None, "offline", False, 0, True, None)
        if recovered:
            return l5._L5Call(result.parsed, "offline-fallback", True, 2, False, None)
        return result
    monkeypatch.setattr(l5, "_complete_json", complete_l5)

    def complete_l6(*args):
        calls.append("L6")
        body = distinctness()
        age = estimate()
        if case == "L6-unknown":
            body.update(distinctness_status="L6_SKIPPED_NO_PARAPHRASE", ambiguity_ablation="SKIPPED",
                        materially_different=None, suppresses_other=None, sense_a_paraphrase="", sense_b_paraphrase="")
        elif case == "L6-negative":
            body.update(distinctness_status="SENSES_TOO_CLOSE", ambiguity_ablation="UNSUPPORTED", materially_different=False)
        elif case in {"L6-invalid", "recovery-invalid"}:
            body = {"invalid": True}
        elif case == "age-unknown":
            age = estimate(understanding="UNKNOWN")
        elif case == "age-barrier":
            age = estimate(understanding="UNLIKELY", barrier="sense_b")
        elif case == "age-content-fail":
            age = estimate(content_appropriate=False, content_quote="crane")
        elif case == "age-content-unknown":
            age = estimate(content_appropriate=None)
        body["age_assessment"] = {"8": {"understanding": "LIKELY"}} if case == "age-invalid" else {"8": age}
        return l6._L6Call(body, "offline-fallback" if recovered else "offline", recovered, 1 if recovered else 0)
    monkeypatch.setattr(l6, "_complete_l6", complete_l6)

    if case.endswith("-error"):
        failed_layer = case.removesuffix("-error")
        def broken(*args):
            raise RuntimeError(f"Controlled {failed_layer} failure")
        monkeypatch.setattr(serve, "_LAYER_REGISTRY", [(name, broken if name == failed_layer else fn)
                                                      for name, fn in runner._LAYER_REGISTRY])
    if case == "setup-error":
        def no_backend():
            raise RuntimeError("Backend unavailable")
        monkeypatch.setattr(serve, "_get_configured_settings", no_backend)
    if case == "payload-error":
        monkeypatch.setattr(serve, "_build_final_payload", lambda *a: (_ for _ in ()).throw(RuntimeError("Bad projection")))
    return calls


async def request_result(stream=True):
    if stream:
        response = await serve.stream_analysis(text=TEXT, target_age=8)
        events = [event async for event in response.body_iterator]
        result = json.loads(next(e.split("data: ", 1)[1] for e in events if e.startswith("event: complete\n")))
        return result, events
    response = await serve.analyze_joke(serve.AnalyzeRequest(text=TEXT, target_age=8))
    return json.loads(response.body), []


def assert_stream_matches_trace(result, events):
    if not events:
        return
    for trace in result["trace"]:
        if trace["layer"] in {"CONFIG", "PAYLOAD"}:
            continue
        event = next(e for e in events if e.startswith(f"event: {trace['layer'].lower()}\n"))
        data = json.loads(event.split("data: ", 1)[1])
        assert data["status"] == trace["status"]
        assert data["reason"] == trace["reason"]
        assert data["provider"] == trace["provider"]


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("layer", ["L0-pre", "L1", "L2", "L3", "L4", "L5", "L6", "L0-post"])
def test_detection_execution_failures_are_never_negative_or_success(monkeypatch, layer, stream):
    prepare_pipeline(monkeypatch, f"{layer}-error")
    result, events = asyncio.run(request_result(stream))
    assert result["detection_status"] == "EXECUTION_FAILED"
    assert result["review_required"]
    assert result["punchline"] is result["sense_a"] is result["sense_b"] is None
    assert result["safety"]["is_safe"] is None
    failed = next(t for t in result["trace"] if t["layer"] == layer)
    assert failed["status"] == "ERROR"
    assert_stream_matches_trace(result, events)


@pytest.mark.parametrize("case", ["L2-unknown", "L3-unknown", "L4-unknown", "L5-unknown", "L6-unknown"])
def test_unknown_and_dependency_skips_are_explicit(monkeypatch, case):
    calls = prepare_pipeline(monkeypatch, case)
    result, events = asyncio.run(request_result())
    assert result["detection_status"] == "INSUFFICIENT_EVIDENCE"
    assert result["punchline"] is None
    assert not result["age_assessment_available"]
    stage = case.split("-")[0]
    trace = result["trace"]
    index = next(i for i, t in enumerate(trace) if t["layer"] == stage)
    assert trace[index]["status"] == "UNKNOWN"
    assert all(t["status"] == "SKIPPED" for t in trace[index + 1:-1])
    assert_stream_matches_trace(result, events)
    if stage in {"L2", "L3"}:
        assert calls == []


@pytest.mark.parametrize("case", ["L4-negative", "L5-negative", "L6-negative"])
def test_assessed_rejections_remain_non_pun(monkeypatch, case):
    prepare_pipeline(monkeypatch, case)
    result, events = asyncio.run(request_result())
    assert result["detection_status"] == "NON_PUN"
    assert not result["review_required"]
    assert not result["age_spectrum"]
    assert_stream_matches_trace(result, events)


@pytest.mark.parametrize("case", ["L7-error", "L8-error", "age-invalid"])
def test_age_failure_preserves_confirmed_detection(monkeypatch, case):
    calls = prepare_pipeline(monkeypatch, case)
    result, events = asyncio.run(request_result())
    assert calls == ["L4", "L5", "L6"]
    assert result["detection_status"] == "PUN"
    assert result["punchline"] == "crane"
    assert result["age_spectrum"]["8"]["assessment_status"] == "EXECUTION_FAILED"
    assert result["safety"]["is_safe"] is None
    assert_stream_matches_trace(result, events)


@pytest.mark.parametrize("case", ["age-unknown", "age-barrier", "age-content-unknown", "age-content-fail"])
def test_unassessed_or_rejected_age_axes_do_not_default_to_suitable(monkeypatch, case):
    prepare_pipeline(monkeypatch, case)
    result, events = asyncio.run(request_result())
    assert result["detection_status"] == "PUN"
    item = result["age_spectrum"]["8"]
    if case == "age-barrier":
        assert item["assessment_status"] == "PARTIAL"
        assert item["appropriateness_status"] == "SKIPPED"
    if case == "age-unknown":
        assert item["assessment_status"] == "UNKNOWN"
    assert result["safety"]["is_safe"] is (False if case == "age-content-fail" else None)
    assert_stream_matches_trace(result, events)


def test_recovery_metadata_survives_all_three_model_stages(monkeypatch):
    calls = prepare_pipeline(monkeypatch, "recovery")
    result, events = asyncio.run(request_result())
    assert calls == ["L4", "L5", "L6"]
    assert result["detection_status"] == "PUN"
    for trace, count in zip([t for t in result["trace"] if t["layer"] in calls], [3, 2, 1]):
        assert trace["provider"] == dict(recorded=True, model_used="offline-fallback", application_retries=count, fallback_used=True)
    assert_stream_matches_trace(result, events)


def test_invalid_l6_keeps_execution_metadata_without_promoting_findings(monkeypatch):
    prepare_pipeline(monkeypatch, "L6-invalid")
    result, events = asyncio.run(request_result())
    assert result["detection_status"] == "EXECUTION_FAILED"
    trace = next(t for t in result["trace"] if t["layer"] == "L6")
    assert trace["provider"]["recorded"] is True
    assert trace["status"] == "ERROR"
    assert result["sense_a"] is None


@pytest.mark.parametrize("case", ["setup-error", "payload-error", "L5-truncated"])
@pytest.mark.parametrize("stream", [False, True])
def test_boundary_failures_use_complete_failure_contract(monkeypatch, case, stream):
    prepare_pipeline(monkeypatch, case)
    result, _ = asyncio.run(request_result(stream))
    assert result["detection_status"] == "EXECUTION_FAILED"
    assert result["suggested_action"] == "RETRY_ANALYSIS"
    assert result["safety"]["content_issues"] == result["safety"]["inference_issues"] == []
    assert result["safety"]["is_safe"] is None


def test_resolving_sense_is_not_inferred_from_a_b_order(monkeypatch):
    prepare_pipeline(monkeypatch, "resolve-a")
    result, _ = asyncio.run(request_result())
    assert result["resolving_sense"] == "sense_a"
    assert result["sense_a"]["is_resolving_sense"]
    assert not result["sense_b"]["is_resolving_sense"]


def test_stream_validates_same_input_bounds_as_post(monkeypatch):
    monkeypatch.setattr(serve, "_get_configured_settings", lambda: pytest.fail("Invalid requests must not configure providers"))
    client = TestClient(serve.app)
    for params in ({"text": "x", "target_age": 3}, {"text": "x", "target_age": 19}, {"text": "x" * 1001}, {"text": ""}):
        assert client.get("/api/analyze/stream", params=params).status_code == 422


def test_waiting_event_reports_the_current_stage_without_inventing_progress(monkeypatch):
    import threading
    prepare_pipeline(monkeypatch)
    original_call = l4._complete_l4
    original_wait = asyncio.wait
    started, release = threading.Event(), threading.Event()
    def delayed(*args):
        started.set()
        assert release.wait(2)
        return original_call(*args)
    async def short_wait(futures, **kwargs):
        await asyncio.sleep(.002)
        if started.is_set() and not release.is_set():
            release.set()
            return set(), set(futures)
        return await original_wait(futures, **kwargs)
    monkeypatch.setattr(l4, "_complete_l4", delayed)
    monkeypatch.setattr(serve.asyncio, "wait", short_wait)
    result, events = asyncio.run(request_result())
    waiting = [json.loads(e.split("data: ", 1)[1]) for e in events if e.startswith("event: waiting\n")]
    assert result["detection_status"] == "PUN"
    assert waiting and all(d["layer"] == "L4" and "no result yet" in d["message"] for d in waiting)


def test_age_switching_uses_age_specific_appropriateness_axes():
    from crack.schema import L7Result, L8Result
    from tests.test_system_design import completed_record
    rec = completed_record(ages=[8, 12])
    rec.l7_result = L7Result(per_age_comprehension={8: "AOA_UNKNOWN", 12: "FULLY_COMPREHENSIBLE"})
    rec.l8_result = L8Result(per_age_verdict={8: "UNKNOWN", 12: "FULLY_AGE_APPROPRIATE"},
                             content_appropriate={8: None, 12: True}, inference_appropriate={8: None, 12: True})
    runner._l0_post_layer(rec, DEFAULT_SETTINGS)
    result = serve._build_final_payload(rec, 8)
    assert result["age_spectrum"][8]["safety"]["is_safe"] is None
    assert result["age_spectrum"][12]["safety"]["is_safe"] is True
    assert result["safety"]["is_safe"] is None


@pytest.mark.parametrize("chain", [(), ("backup",)])
def test_exhausted_single_model_is_not_reported_as_model_fallback(monkeypatch, chain):
    tried = []
    def exhausted(prompt, model, *args):
        tried.append(model)
        return None, 3, RuntimeError("Service failure")
    monkeypatch.setattr(l4, "_call_gemini_l4_single", exhausted)
    settings = DEFAULT_SETTINGS.model_copy(update={"L4_MODEL_GEMINI": "primary", "L4_MODEL_GEMINI_CHAIN": chain})
    result = l4._call_gemini_l4("offline", settings, client=object())
    assert tried == ["primary", *chain]
    assert result.fallback_used is bool(chain)


def test_service_recovery_cannot_turn_invalid_output_into_a_success(monkeypatch):
    prepare_pipeline(monkeypatch, "recovery-invalid")
    result, events = asyncio.run(request_result())
    assert result["detection_status"] == "EXECUTION_FAILED"
    assert result["punchline"] is result["confidence"] is None
    assert all(t["provider"]["fallback_used"] for t in result["trace"] if t["layer"] in {"L4", "L5", "L6"})
    assert_stream_matches_trace(result, events)
