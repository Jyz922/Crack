"""L4 schema, prompt, and provider contract tests, without live requests."""

import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from pydantic import ValidationError

from crack.config import DEFAULT_SETTINGS
from crack.enums import AnchoringStatus, Genre
from crack.l1_surface import analyze
from crack.l4_anchoring import _align_substring, _complete_l4, _render_l4_prompt, anchor_l4
from crack.schema import AnalysisRecord, CandidateEntry, L3Result, L4Result
from crack.validation import ModelResponseError, validate_l4_response


@pytest.mark.parametrize("backend", ["openai", "anthropic", "gemini"])
def test_providers_preserve_raw_responses_and_share_one_correction(backend):
    text = "The seal kept the envelope closed beside a swimming seal."
    p = {
        "target_term": "seal", "split_parts": [],
        "sense_a": "a closure", "sense_a_anchor_quote": "envelope closed",
        "sense_b": "a marine animal", "sense_b_anchor_quote": "swimming seal",
        "anchor_relation": "separate_contexts", "anchoring_status": "PASS",
        "resolving_sense": "sense_b", "reasoning": "The two contexts support two meanings.",
    }
    replies = iter(["not json", json.dumps(p)])
    requests = []

    def create(**kwargs):
        requests.append(kwargs)
        raw = next(replies)
        return NS(
            text=raw, candidates=[NS(finish_reason="STOP")],
            stop_reason="end_turn", content=[NS(text=raw)],
            choices=[NS(finish_reason="stop", message=NS(content=raw, refusal=None))],
        )

    client = NS(chat=NS(completions=NS(create=create)), messages=NS(create=create),
                models=NS(generate_content=create))
    r = AnalysisRecord(item_id="unseen_provider", text=text, target_ages=[8], l1_result=analyze(text),
                       l3_result=L3Result(candidates=[CandidateEntry(term="seal", score=0.7)], total_terms=1))
    settings = DEFAULT_SETTINGS.model_copy(update={"L4_BACKEND": backend})
    result = anchor_l4(r, settings, client=client)
    assert result.anchoring_status == AnchoringStatus.PASS
    assert len(requests) == 2
    assert [a.accepted for a in r.l4_attempts] == [False, True]
    assert r.l4_attempts[0].raw_responses == ["not json"]
    assert json.loads(r.l4_attempts[1].raw_responses[0]) == p


def test_pass_requires_resolving_sense():
    with pytest.raises(ValidationError):
        L4Result(sense_a="one", sense_b="two", sense_a_anchor_quote="left",
                 sense_b_anchor_quote="right", anchoring_status=AnchoringStatus.PASS)


def test_missing_prerequisite_is_not_assessed():
    r = AnalysisRecord(item_id="unseen_missing", text="A short sentence.", target_ages=[8])
    with pytest.raises(ValueError, match="L1 must run"):
        anchor_l4(r)


def test_unknown_backend_is_rejected():
    settings = DEFAULT_SETTINGS.model_copy(update={"L4_BACKEND": "unknown_backend"})
    with pytest.raises(ValueError):
        _complete_l4("prompt", settings, None)


def test_prompt_has_no_unexpanded_variables():
    rendered = _render_l4_prompt("A short sentence.", Genre.DECLARATIVE, "sentence", "dictionary proposal")
    for placeholder in ("{text}", "{genre}", "{candidate_term}", "{candidate_details}"):
        assert placeholder not in rendered
    assert "Candidate ambiguous term: sentence" in rendered


@pytest.mark.parametrize("quote,text,expected", [
    ("draft", "a draft", "draft"),
    ("DRAFT", "a draft", "draft"),
    ('"draft."', "a draft.", "draft"),
])
def test_optional_alignment_utility(quote, text, expected):
    assert _align_substring(quote, text) == expected


def test_optional_alignment_does_not_relax_runtime_contract():
    p = {"target_term": "draft", "split_parts": [], "sense_a": "a text version",
         "sense_a_anchor_quote": "DRAFT", "sense_b": "", "sense_b_anchor_quote": "",
         "anchoring_status": "ONE_SENSE_ONLY", "anchor_relation": None, "resolving_sense": None,
         "reasoning": "Only one reading is grounded."}
    with pytest.raises(ModelResponseError, match="verbatim"):
        validate_l4_response(p, "a draft", "draft", False)


def test_historical_fixture_records_remain_readable_without_claiming_current_validation():
    path = Path(__file__).parent / "fixtures" / "l5_anchors.jsonl"
    for line in path.read_text().splitlines():
        data = json.loads(line)["l4_result"]
        result = L4Result.model_validate(data)
        assert result.target_term == ""
        with pytest.raises(ModelResponseError, match="Response fields"):
            validate_l4_response(data, "historical source", "term", False)
