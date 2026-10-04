"""Age comprehension consumes the existing L6 response; no provider requests."""
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from crack import age_evidence, l7_comprehension as l7
from crack.config import DEFAULT_SETTINGS
from crack.schema import L7Result
from crack.validation import ModelResponseError
from tests.test_system_design import completed_record


def estimate(**changes):
    value = dict(understanding="LIKELY", barrier=None, content_appropriate=True,
                 inference_appropriate=True, reason="These conventional readings are familiar at this age.",
                 content_quote="", prerequisite="")
    value.update(changes)
    return value


@pytest.fixture
def rated_words(monkeypatch):
    monkeypatch.setattr(age_evidence, "aoa_lookup", lambda word: (6.2, "exact") if word == "crane" else (None, "miss"))
    monkeypatch.setattr(l7, "resource_sha256", lambda: "a" * 64)


def cached_record(**changes):
    rec = completed_record(ages=[8])
    rec.l6_result.age_assessment = {"8": estimate(**changes)}
    return rec


@pytest.mark.parametrize("understanding,barrier,status", [
    ("LIKELY", None, "FULLY_COMPREHENSIBLE"),
    ("UNLIKELY", "vocabulary", "PARTIALLY_COMPREHENSIBLE"),
    ("UNLIKELY", "sense_a", "PARTIALLY_COMPREHENSIBLE"),
    ("UNLIKELY", "sense_b", "SENSE_B_TOO_ADVANCED"),
    ("UNLIKELY", "wordplay", "WORDPLAY_SKILL_TOO_ADVANCED"),
    ("UNLIKELY", "background_knowledge", "WORDPLAY_SKILL_TOO_ADVANCED"),
    ("UNKNOWN", None, "AOA_UNKNOWN"),
])
def test_comprehension_uses_cached_finding_without_numeric_age_defaults(rated_words, understanding, barrier, status):
    rec = cached_record()
    rec.l6_result.age_assessment["8"].update(understanding=understanding, barrier=barrier)
    client = MagicMock()
    result = l7.assess_l7(rec, DEFAULT_SETTINGS, client=client)
    assert result.per_age_comprehension[8].value == status
    assert result.sense_a_aoa is result.sense_b_aoa is result.metalinguistic_floor is None
    client.models.generate_content.assert_not_called()
    client.messages.create.assert_not_called()
    client.chat.completions.create.assert_not_called()


def test_word_citations_come_from_local_lookup_and_misses_remain_null(rated_words):
    result = l7.assess_l7(cached_record())
    citations = {entry.word: entry for entry in result.aoa_evidence}
    assert citations["crane"].aoa == 6.2
    assert citations["nested"].aoa is None
    assert citations["nested"].match == "miss"
    assert result.per_age_estimates[8].reason == estimate()["reason"]


def test_missing_shared_age_answer_is_failure_without_fallback(rated_words):
    rec = completed_record(ages=[8])
    client = MagicMock()
    with pytest.raises(ModelResponseError):
        l7.assess_l7(rec, client=client)
    client.models.generate_content.assert_not_called()


@pytest.mark.parametrize("change", [
    {"understanding": "maybe"}, {"content_appropriate": "true"},
    {"reason": ""}, {"barrier": "wordplay"}, {"extra": "invented"},
])
def test_malformed_estimates_are_rejected_without_repair(rated_words, change):
    rec = cached_record()
    rec.l6_result.age_assessment["8"].update(change)
    with pytest.raises((ModelResponseError, ValidationError)):
        l7.assess_l7(rec)


def test_requested_ages_must_match_without_default_eight(rated_words):
    rec = cached_record()
    rec.l6_result.age_assessment = {"6": estimate()}
    with pytest.raises(ModelResponseError):
        l7.assess_l7(rec)


def test_unknown_understanding_does_not_invent_a_specific_unknown_prerequisite(rated_words):
    rec = cached_record()
    rec.l6_result.age_assessment["8"]["understanding"] = "UNKNOWN"
    summary = l7.assess_l7(rec).per_age_summaries[8]
    assert summary.barrier_dimensions == []
    assert summary.unknown_dimensions == ["understanding"]
    assert not summary.fully_assessed


def test_historical_age_records_remain_readable():
    result = L7Result(per_age_comprehension={8: "FULLY_COMPREHENSIBLE"}, sense_a_aoa=5.0)
    assert result.sense_a_aoa == 5.0
    assert not result.per_age_estimates
