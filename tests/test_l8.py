"""Appropriateness is local, preserves unknowns, and requires real evidence."""
import pytest

from crack import age_evidence, l7_comprehension as l7, l8_appropriateness as l8, runner
from crack.config import DEFAULT_SETTINGS
from crack.validation import ModelResponseError
from tests.test_l7 import cached_record, estimate


@pytest.fixture(autouse=True)
def local_age_resources(monkeypatch):
    monkeypatch.setattr(age_evidence, "aoa_lookup", lambda word: (None, "miss"))
    monkeypatch.setattr(l7, "resource_sha256", lambda: "b" * 64)


def assessed_record(**changes):
    rec = cached_record()
    rec.l6_result.age_assessment["8"].update(changes)
    rec.l7_result = l7.assess_l7(rec)
    return rec


@pytest.mark.parametrize("content,inference,expected", [
    (True, True, "FULLY_AGE_APPROPRIATE"),
    (None, True, "UNKNOWN"), (True, None, "UNKNOWN"), (None, None, "UNKNOWN"),
])
def test_axes_preserve_unknown_and_never_default_to_approval(content, inference, expected):
    result = l8.assess_l8(assessed_record(content_appropriate=content, inference_appropriate=inference))
    assert result.per_age_verdict[8].value == expected
    assert result.content_appropriate[8] is content
    assert result.inference_appropriate[8] is inference


def test_content_rejection_requires_actual_source_quote():
    rec = assessed_record(content_appropriate=False, content_quote="lifted a crate")
    assert l8.assess_l8(rec).per_age_verdict[8].value == "CONTENT_NOT_APPROPRIATE"
    rec.l7_result.per_age_estimates[8].content_quote = "an invented event"
    with pytest.raises(ModelResponseError, match="verbatim"):
        l8.assess_l8(rec)


def test_content_rejection_without_quote_is_not_filled_in():
    with pytest.raises(ModelResponseError):
        l8.assess_l8(assessed_record(content_appropriate=False))


def test_inference_rejection_needs_named_prerequisite():
    rec = assessed_record(inference_appropriate=False, prerequisite="knowledge of a specialized occupation")
    result = l8.assess_l8(rec)
    assert result.per_age_verdict[8].value == "CONTENT_OK_INFERENCE_TOO_ADVANCED"
    assert result.inference_issues == ["knowledge of a specialized occupation"]
    rec.l7_result.per_age_estimates[8].prerequisite = ""
    with pytest.raises(ModelResponseError):
        l8.assess_l8(rec)


@pytest.mark.parametrize("understanding,barrier", [("UNKNOWN", None), ("UNLIKELY", "vocabulary")])
def test_l7_unknown_or_rejection_stops_l8(understanding, barrier):
    rec = assessed_record(understanding=understanding, barrier=barrier)
    calls = []
    runner.execute_layer("L8", lambda *args: calls.append(args), rec, DEFAULT_SETTINGS)
    assert not calls
    assert rec.trace[-1].status == "SKIPPED"
    runner._l0_post_layer(rec, DEFAULT_SETTINGS)
    assert rec.final.detection_status.value == "PUN"
    assert rec.final.per_age[8].appropriateness.value == "UNKNOWN"


def test_multiple_ages_are_independent_and_l8_uses_only_l7_passes():
    rec = cached_record()
    rec.target_ages = [6, 8]
    rec.l6_result.age_assessment["6"] = estimate()
    rec.l6_result.age_assessment["6"]["understanding"] = "UNKNOWN"
    rec.l7_result = l7.assess_l7(rec)
    result = l8.assess_l8(rec)
    assert result.per_age_verdict[6].value == "UNKNOWN"
    assert result.content_appropriate[6] is None
    assert result.per_age_verdict[8].value == "FULLY_AGE_APPROPRIATE"


def test_l8_requires_completed_comprehension():
    with pytest.raises(ModelResponseError):
        l8.assess_l8(cached_record())
