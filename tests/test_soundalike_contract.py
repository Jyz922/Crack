"""Soundalike contract (handoff 03): L4 response shape, local verification of
alternates, hyphen resegmentation, labels and versions. Offline."""
from __future__ import annotations

import pytest

from crack.decisions import CANDIDATE_SEARCH_VERSION
from crack.enums import DetectionStatus, MainClassification, detection_status_for
from crack.schema import Alternate
from crack.validation import RESPONSE_CONTRACT_VERSION, ModelResponseError, validate_l4_response

T1 = "When the band broke up, it wasn’t drama — it was just drum!"
T2 = "Why did the cat stop dating the cad? Because she realized he was only purr-suing her for his own gain!"
T3 = "Why did the cat start working at a bank? Because she wanted to turn her cat-nap into cash."
PURSUING = Alternate(form="pursuing", phones=["P", "ER0", "S", "UW", "IH", "NG"], sim=1.0, sim_cal=1.0,
                     source="hyphen_merge")


def sound(term="purr-suing", relation="sound_substitution", alternate="pursuing", **changes):
    p = {
        "target_term": term, "split_parts": [], "alternate_form": alternate,
        "sense_a": "making a cat's purring sound", "sense_a_anchor_quote": "the cat",
        "sense_b": "romantically chasing someone", "sense_b_anchor_quote": "stop dating the cad",
        "anchor_relation": relation, "anchoring_status": "PASS", "resolving_sense": "sense_b",
        "reasoning": "The cat cue evokes purr; the dating cue evokes pursuing.",
    }
    p.update(changes)
    return p


def test_eleven_keys_required():
    validate_l4_response(sound(), T2, "purr-suing", False, alternates=[PURSUING])
    old = sound(); del old["alternate_form"]
    with pytest.raises(ModelResponseError, match=r"missing=\['alternate_form'\]"):
        validate_l4_response(old, T2, "purr-suing", False, alternates=[PURSUING])


def test_supplied_alternate_is_accepted_without_rescoring():
    out = validate_l4_response(sound(), T2, "purr-suing", False, alternates=[PURSUING])
    assert out["alternate_form"] == "pursuing"


def test_unsupplied_alternate_is_verified_phonetically():
    # Not supplied, but it really does sound the same: accepted.
    validate_l4_response(sound(), T2, "purr-suing", False, alternates=[])
    # A forced sound link (the documented LLM failure) is rejected.
    with pytest.raises(ModelResponseError, match="does not sound like"):
        validate_l4_response(sound(alternate="chasing"), T2, "purr-suing", False, alternates=[])


def test_alternate_without_pronunciation_is_rejected():
    with pytest.raises(ModelResponseError, match="no pronunciation"):
        validate_l4_response(sound(alternate="xqzzt"), T2, "purr-suing", False, alternates=[])


def test_sound_pair_needs_both_words_in_text():
    pair = sound(term="drum", relation="sound_pair", alternate="drama",
                 sense_a="a percussion instrument", sense_a_anchor_quote="the band",
                 sense_b="interpersonal conflict", sense_b_anchor_quote="broke up")
    drama = Alternate(form="drama", phones=["D", "R", "AA", "M", "AH0"], sim=0.8897, sim_cal=0.5949,
                      source="in_text")
    validate_l4_response(pair, T1, "drum", False, alternates=[drama])
    with pytest.raises(ModelResponseError, match="sound_pair requires"):
        validate_l4_response({**pair, "alternate_form": "dram"}, T1, "drum", False, alternates=[drama])
    # drum/drama (0.890) clears the finder's p95 but not the p99 bar for
    # alternates the model proposes on its own.
    with pytest.raises(ModelResponseError, match="does not sound like"):
        validate_l4_response(pair, T1, "drum", False, alternates=[])


def test_alternate_only_on_soundalike_pass():
    with pytest.raises(ModelResponseError, match="only allowed"):
        validate_l4_response(sound(anchor_relation="separate_contexts"), T2, "purr-suing", False)
    non_pass = sound(anchoring_status="ONE_SENSE_ONLY", anchor_relation=None, resolving_sense=None,
                     sense_b="", sense_b_anchor_quote="")
    with pytest.raises(ModelResponseError, match="only allowed"):
        validate_l4_response(non_pass, T2, "purr-suing", False)
    with pytest.raises(ModelResponseError, match="requires alternate_form"):
        validate_l4_response(sound(alternate=None), T2, "purr-suing", False)


def test_soundalike_quotes_follow_the_non_split_rule():
    with pytest.raises(ModelResponseError, match="different context spans"):
        validate_l4_response(sound(sense_a_anchor_quote="purr-suing"), T2, "purr-suing", False,
                             alternates=[PURSUING])


def test_hyphenated_resegmentation_is_accepted():
    split = {
        "target_term": "cat-nap", "split_parts": ["cat", "nap"], "alternate_form": None,
        "sense_a": "a short sleep", "sense_a_anchor_quote": "cat-nap",
        "sense_b": "the cat's own nap", "sense_b_anchor_quote": "cat-nap",
        "anchor_relation": "resegmentation", "anchoring_status": "PASS", "resolving_sense": "sense_b",
        "reasoning": "The whole word and its parts both apply to the cat.",
    }
    validate_l4_response(split, T3, "cat-nap", True, [("cat", "nap")])
    with pytest.raises(ModelResponseError, match="supplied segmentation"):
        validate_l4_response({**split, "split_parts": ["ca", "tnap"]}, T3, "cat-nap", True, [("cat", "nap")])


def test_labels_and_versions():
    assert detection_status_for(MainClassification.VALID_SOUNDALIKE_JOKE) == DetectionStatus.PUN
    assert detection_status_for(MainClassification.OUT_OF_SCOPE_HOMOPHONE) == DetectionStatus.OUT_OF_SCOPE
    assert (RESPONSE_CONTRACT_VERSION, CANDIDATE_SEARCH_VERSION) == ("7", "5")


# --- Sub-step B: L3 soundalike entries with a separate budget -------------

def _l3(text, **settings):
    from crack.config import Settings
    from crack.layers import run_l1, run_l2, run_l3
    from crack.schema import AnalysisRecord

    s = Settings(**settings)
    return run_l3(run_l2(run_l1(AnalysisRecord(item_id="t", text=text, target_ages=[]), s), s), s).l3_result


def test_soundalike_appended_after_unchanged_homograph_slots():
    with_sa, without = _l3(T2), _l3(T2, L3_SOUNDALIKE_TOP_K=0)
    assert [c.term for c in with_sa.candidates[:8]] == [c.term for c in without.candidates]
    extra = with_sa.candidates[8]
    assert extra.term == "purr-suing"
    assert [a.form for a in extra.soundalike_alternates] == ["pursuing"]
    assert extra.score_components["soundalike"] == 1.0
    assert extra.score_components["phonetic_sim"] == 1.0


def test_soundalike_on_existing_slot_only_gains_alternates():
    result = _l3(T1)
    drum = next(c for c in result.candidates if c.term == "drum")
    assert [a.form for a in drum.soundalike_alternates] == ["drama"]
    assert len(result.candidates) == len(_l3(T1, L3_SOUNDALIKE_TOP_K=0).candidates)


def test_zero_soundalike_budget_is_the_old_ranking():
    result = _l3(T2, L3_SOUNDALIKE_TOP_K=0)
    assert all(not c.soundalike_alternates for c in result.candidates)


# --- Sub-step C: L4 prompt, shortlist and single-request validation ---------

def _through_l3_record(text):
    from crack.config import DEFAULT_SETTINGS
    from crack.layers import run_l1, run_l2, run_l3
    from crack.schema import AnalysisRecord

    r = AnalysisRecord(item_id="t", text=text, target_ages=[])
    return run_l3(run_l2(run_l1(r, DEFAULT_SETTINGS), DEFAULT_SETTINGS), DEFAULT_SETTINGS)


def _mock_l4(monkeypatch, body):
    import json
    from crack import l4_anchoring as l4

    calls = []

    def complete(prompt, settings, client, response_log=None):
        calls.append(prompt)
        response_log.append(json.dumps(body))
        return l4._L4Call(body, "offline", False, 0)

    monkeypatch.setattr(l4, "_complete_l4", complete)
    return calls


def test_gemini_schema_has_alternate_form():
    from crack.l4_anchoring import _L4LLMResponse
    assert "alternate_form" in _L4LLMResponse.model_fields


def test_l4_sees_soundalike_candidate_and_its_alternate(monkeypatch):
    import json
    from crack import l4_anchoring as l4

    record = _through_l3_record(T2)
    calls = _mock_l4(monkeypatch, sound())
    result = l4.anchor_l4(record)
    assert len(calls) == 1
    assert "purr-suing" in record.l4_search.considered_terms  # kept beyond the homograph top-8
    details = json.loads(calls[0].split("Dictionary proposals are possibilities, not contextual evidence.\n", 1)[1]
                         .split("\n", 1)[0])
    purr = next(p for p in details if p["term"] == "purr-suing")
    alt = purr["soundalike_alternates"][0]
    assert (alt["form"], alt["relation"], alt["phonetic_similarity"]) == ("pursuing", "sound_substitution", 1.0)
    assert alt["dictionary_proposals"]  # the alternate's own senses
    assert not any(sid.startswith("pursue") for sid, _ in purr["dictionary_proposals"])
    assert result.alternate_form == "pursuing" and result.anchor_relation.value == "sound_substitution"


def test_forced_sound_link_fails_after_one_request(monkeypatch):
    from crack import l4_anchoring as l4

    record = _through_l3_record(T2)
    calls = _mock_l4(monkeypatch, sound(alternate="chasing"))
    with pytest.raises(ModelResponseError, match="does not sound like"):
        l4.anchor_l4(record)
    assert len(calls) == 1 and not record.l4_attempts[0].accepted


def test_prompt_declares_eleven_keys_and_both_relations():
    from crack.l4_anchoring import _load_prompt
    prompt = _load_prompt()
    assert "exactly these eleven keys" in prompt and '"alternate_form": null' in prompt
    assert "sound_substitution" in prompt and "sound_pair" in prompt
