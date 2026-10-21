"""Soundalike workstream 03, end to end with mocked model stages (offline).

The real L0-L3 stages run (WordNet, CMUdict, phonetics); only the L4, L5 and
L6 model calls are replaced. Each text checks the final label, the scope and
that every model stage is called at most once.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from crack import age_evidence, l4_anchoring as l4, l5_resolution as l5, l6_distinctness as l6
from crack import l7_comprehension as l7, runner, serve
from crack.config import DEFAULT_SETTINGS
from crack.enums import DetectionStatus, MainClassification, ScopeLabel, detection_status_for
from crack.schema import AnalysisRecord, LayerTrace
from tests.test_l7 import estimate
from tests.test_system_design import distinctness, fake_l5

T1 = "When the band broke up, it wasn’t drama — it was just drum!"
T2 = "Why did the cat stop dating the cad? Because she realized he was only purr-suing her for his own gain!"
T3 = "Why did the cat start working at a bank? Because she wanted to turn her cat-nap into cash."

L4_BODIES = {
    T1: {
        "target_term": "drum", "split_parts": [], "alternate_form": "drama",
        "sense_a": "a percussion instrument", "sense_a_anchor_quote": "the band",
        "sense_b": "emotional conflict between people", "sense_b_anchor_quote": "broke up",
        "anchor_relation": "sound_pair", "anchoring_status": "PASS", "resolving_sense": "sense_a",
        "reasoning": "The band cue supports a drum; the breakup cue supports drama; the punchline swaps them.",
    },
    T2: {
        "target_term": "purr-suing", "split_parts": [], "alternate_form": "pursuing",
        "sense_a": "making a cat's purring sound", "sense_a_anchor_quote": "the cat",
        "sense_b": "romantically chasing someone", "sense_b_anchor_quote": "stop dating the cad",
        "anchor_relation": "sound_substitution", "anchoring_status": "PASS", "resolving_sense": "sense_b",
        "reasoning": "The cat cue evokes purr; the dating cue evokes pursuing.",
    },
    T3: {
        "target_term": "cat-nap", "split_parts": ["cat", "nap"], "alternate_form": None,
        "sense_a": "a short light sleep", "sense_a_anchor_quote": "cat-nap",
        "sense_b": "a nap taken by the cat", "sense_b_anchor_quote": "cat-nap",
        "anchor_relation": "resegmentation", "anchoring_status": "PASS", "resolving_sense": "sense_b",
        "reasoning": "The whole word means a short sleep; split, it is the cat's own nap.",
    },
}


@pytest.fixture
def mocked_models(monkeypatch):
    calls: list[str] = []
    prompts: dict[str, str] = {}
    monkeypatch.setattr(age_evidence, "aoa_lookup", lambda word: (5.0, "exact"))
    monkeypatch.setattr(l7, "resource_sha256", lambda: "a" * 64)

    def complete_l4(prompt, settings, client, response_log=None):
        calls.append("L4")
        prompts["L4"] = prompt
        body = next(b for t, b in L4_BODIES.items() if t in prompt)
        if response_log is not None:
            response_log.append(json.dumps(body))
        return l4._L4Call(body, "offline", False, 0)

    monkeypatch.setattr(l4, "_complete_l4", complete_l4)
    seen_l5 = fake_l5(monkeypatch)
    original_l5 = l5._complete_json

    def complete_l5(prompt, *args, **kwargs):
        calls.append("L5")
        prompts["L5"] = prompt
        return original_l5(prompt, *args, **kwargs)

    monkeypatch.setattr(l5, "_complete_json", complete_l5)

    def complete_l6(prompt, *args):
        calls.append("L6")
        prompts["L6"] = prompt
        body = distinctness()
        body["age_assessment"] = {"8": estimate()}
        return l6._L6Call(body, "offline", False, 0)

    monkeypatch.setattr(l6, "_complete_l6", complete_l6)
    return calls, prompts


def run_pipeline(text, ages=(8,)):
    record = AnalysisRecord(item_id="e2e", text=text, target_ages=list(ages))
    for name, fn in runner._LAYER_REGISTRY:  # mirrors runner.run's per-layer error handling
        try:
            record = runner.execute_layer(name, fn, record, DEFAULT_SETTINGS)
        except Exception as exc:
            record.trace.append(LayerTrace(layer=name, status="ERROR", reason=f"{type(exc).__name__}: {exc}",
                                           duration_ms=0, hints_used=0))
    return record


@pytest.mark.parametrize("text,label,scope", [
    (T2, MainClassification.VALID_SOUNDALIKE_JOKE, ScopeLabel.SOUNDALIKE),
    (T1, MainClassification.VALID_SOUNDALIKE_JOKE, ScopeLabel.SOUNDALIKE),
    (T3, MainClassification.VALID_COMPOUND_SPLIT_JOKE, ScopeLabel.COMPOUND_SPLIT),
])
def test_three_texts_end_to_end(mocked_models, text, label, scope):
    calls, _ = mocked_models
    record = run_pipeline(text)
    errors = [t for t in record.trace if t.status in {"ERROR", "REJECTED"}]
    assert not errors, errors
    assert record.final.main_classification == label, record.final.review_reason
    assert record.final.scope_label == scope
    assert detection_status_for(record.final.main_classification) == DetectionStatus.PUN
    assert set(record.final.per_age) == {8}
    assert calls == ["L4", "L5", "L6"]  # one request per model stage


def test_soundalike_prompts_carry_the_mechanism(mocked_models):
    _, prompts = mocked_models
    run_pipeline(T2)
    assert '"form": "pursuing"' in prompts["L4"]
    assert 'evokes the absent, similar-sounding "pursuing"' in prompts["L5"]
    assert 'evokes the absent, similar-sounding "pursuing"' in prompts["L6"]


def test_forced_alternate_ends_as_execution_failure(mocked_models, monkeypatch):
    calls, _ = mocked_models
    monkeypatch.setitem(L4_BODIES, T2, {**L4_BODIES[T2], "alternate_form": "chasing"})
    record = run_pipeline(T2)
    assert record.final.main_classification == MainClassification.EXECUTION_FAILED
    assert "does not sound like" in next(t.reason for t in record.trace if t.layer == "L4")
    assert calls == ["L4"]  # rejected without a corrective request; L5/L6 never run


def test_web_result_shows_soundalike_joke(mocked_models):
    async def request():
        response = await serve.analyze_joke(serve.AnalyzeRequest(text=T2, target_age=8))
        return json.loads(response.body)

    result = asyncio.run(request())
    assert result["main_classification"] == "VALID_SOUNDALIKE_JOKE"
    assert result["detection_status"] == "PUN"
    assert (result["punchline"], result["alternate_form"]) == ("purr-suing", "pursuing")
    assert result["anchor_relation"] == "sound_substitution"
