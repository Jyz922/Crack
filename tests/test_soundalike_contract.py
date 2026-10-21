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
