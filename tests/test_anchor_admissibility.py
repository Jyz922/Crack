"""Structural anchor rules using constructed inputs, never benchmark IDs.

Acceptance here means a source anchor is admissible, not that a text is funny.
"""
from copy import deepcopy

import pytest

from crack.enums import Genre
from crack.l1_surface import route_genre
from crack.validation import AlternateNotVerified, ModelResponseError, validate_l4_response


def response(term, qa, qb, **changes):
    value = {"target_term": term, "sense_a": "a conventional reading",
             "sense_b": "a different proposed reading", "sense_a_anchor_quote": qa,
             "sense_b_anchor_quote": qb, "split_parts": [], "alternate_form": None,
             "anchor_relation": "separate_contexts", "anchoring_status": "PASS",
             "resolving_sense": "sense_b", "reasoning": "These are proposed links to check downstream."}
    value.update(changes)
    return value


def split_response(qa, qb):
    return response("sunflower", qa, qb, anchor_relation="resegmentation", split_parts=["sun", "flower"])


def check_split(value, text, audit=None, **kwargs):
    return validate_l4_response(value, text, "sunflower", True, [("sun", "flower")], anchor_audit=audit, **kwargs)


def test_split_narrows_only_source_span_and_preserves_raw_response():
    text = "She inspected her Sunflower beside the window."
    value = split_response("her Sunflower", "Sunflower beside the window")
    before = deepcopy(value)
    audit = []
    out = check_split(value, text, audit)
    assert value == before
    assert out["sense_a_anchor_quote"] == out["sense_b_anchor_quote"] == "Sunflower"
    assert len(audit) == 2
    for event in audit:
        assert event["rule"] == "split_token_narrowing"
        assert text[slice(*event["source_span"])] == event["accepted_quote"]
    for key in value.keys() - {"sense_a_anchor_quote", "sense_b_anchor_quote"}:
        assert out[key] == value[key]


@pytest.mark.parametrize("text,quote", [
    ("A sunflower met another sunflower.", "A sunflower"),
    ("A presunflower opened.", "A presunflower"),
    ("A sunflower-like ornament fell.", "A sunflower-like ornament"),
    ("The sunflower's petals opened.", "The sunflower's petals"),
    ("A sunflower2 opened.", "A sunflower2"),
    ("Her sunflower opened.", "Her SUNFLOWER"),
    ("Her sunflower opened beside a window.", "beside a window"),
])
def test_split_rejects_ambiguous_partial_or_nonverbatim_enclosures(text, quote):
    audit = []
    with pytest.raises(ModelResponseError):
        check_split(split_response(quote, quote), text, audit)
    assert audit == []


def test_split_still_requires_detected_candidate_and_supplied_parts():
    text = "A sunflower opened."
    value = split_response(text, text)
    with pytest.raises(ModelResponseError, match="detected compound"):
        validate_l4_response(value, text, "sunflower", False, [("sun", "flower")])
    with pytest.raises(ModelResponseError, match="supplied segmentation"):
        validate_l4_response(value, text, "sunflower", True, [("sunf", "lower")])


@pytest.mark.parametrize("swap", [False, True])
@pytest.mark.parametrize("relation,alternate", [("separate_contexts", None), ("sound_substitution", "key")])
def test_definition_head_is_structural_and_not_limited_to_soundalikes(swap, relation, alternate):
    text = "Quay: a keyboard berth for a returning sailor."
    qa, qb = ("Quay", "keyboard berth") if not swap else ("keyboard berth", "Quay")
    value = response("quay", qa, qb, anchor_relation=relation, alternate_form=alternate)
    before = deepcopy(value)
    audit = []
    out = validate_l4_response(value, text, "quay", False, anchor_audit=audit)
    assert route_genre(text) == Genre.DEFINITIONAL_ONELINER
    assert value == before and out == {**value, "target_term": "quay"}
    assert len(audit) == 1 and audit[0]["rule"] == "definition_head_anchor"
    assert text[slice(*audit[0]["source_span"])] == "Quay"
    assert text[slice(*audit[0]["body_source_span"])] == "keyboard berth"


@pytest.mark.parametrize("text,qa,qb", [
    ("A quay serves a keyboard berth.", "quay", "keyboard berth"),
    ("Preface. Quay: a keyboard berth.", "Quay", "keyboard berth"),
    ("Quay: a keyboard berth.", "Quay", "Quay"),
    ("Quay: a keyboard berth.", "Quay", "Quay: a keyboard berth."),
    ("Quay: a keyboard berth by another keyboard berth.", "Quay", "keyboard berth"),
    ("Quay:", "Quay", "Quay"),
    ("Quay: a keyboard berth.", "quay", "keyboard berth"),
])
def test_definition_exception_rejects_missing_heading_shared_or_ambiguous_anchors(text, qa, qb):
    audit = []
    with pytest.raises(ModelResponseError):
        validate_l4_response(response("quay", qa, qb), text, "quay", False, anchor_audit=audit)
    assert audit == []


def test_definition_still_checks_phonetics_and_commits_no_audit_on_failure():
    text = "Quay: a keyboard berth for a returning sailor."
    audit = []
    with pytest.raises(AlternateNotVerified):
        validate_l4_response(response("quay", "Quay", "keyboard berth",
            anchor_relation="sound_substitution", alternate_form="elephant"), text, "quay", False,
            anchor_audit=audit)
    assert audit == []


def test_definition_does_not_turn_a_negative_into_a_pass():
    text = "Quay: a keyboard berth for a returning sailor."
    value = response("quay", "Quay", "", sense_b="", anchoring_status="ONE_SENSE_ONLY",
                     anchor_relation=None, resolving_sense=None)
    audit = []
    out = validate_l4_response(value, text, "quay", False, anchor_audit=audit)
    assert out["anchoring_status"] == "ONE_SENSE_ONLY" and audit == []


def test_live_path_keeps_original_reply_and_records_validated_anchor_view(monkeypatch):
    from types import SimpleNamespace
    from crack.config import DEFAULT_SETTINGS
    import crack.l4_anchoring as l4
    from crack.schema import AnalysisRecord, CandidateEntry

    text = "She inspected her Sunflower beside the window."
    raw = split_response("her Sunflower", "Sunflower beside the window")
    original = deepcopy(raw)
    monkeypatch.setattr(l4, "_complete_l4", lambda *args: SimpleNamespace(
        parsed=raw, model_used="offline", retries=0, fallback_used=False))
    record = AnalysisRecord(item_id="synthetic", text=text, target_ages=[])
    candidate = CandidateEntry(term="sunflower", score=1, split_options=[("sun", "flower")],
                               score_components={"compound_split": 1})
    result = l4._anchor_shortlist(record, Genre.DECLARATIVE, [candidate], DEFAULT_SETTINGS, None)
    attempt = record.l4_attempts[0]
    assert raw == original == attempt.parsed_response
    assert result.sense_a_anchor_quote == "Sunflower"
    assert attempt.validated_response["sense_a_anchor_quote"] == "Sunflower"
    assert len(attempt.anchor_adjustments) == 2 and attempt.accepted
