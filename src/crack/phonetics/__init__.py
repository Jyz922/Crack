"""Local phonetic evidence for soundalike wordplay (no provider calls).

See docs/soundalike/handoff/01_phonetic_core.md.
"""
from crack.phonetics.calibration import calibrate
from crack.phonetics.lexicon import lookup_source, pronunciations, span_phones, to_feature_vectors
from crack.phonetics.similarity import (
    FEATURE_WEIGHTS,
    MissingPronunciation,
    SoundScore,
    phone_distance,
    sound_similarity,
    weighted_levenshtein,
)

__all__ = [
    "FEATURE_WEIGHTS", "MissingPronunciation", "SoundScore", "calibrate", "lookup_source",
    "phone_distance", "pronunciations", "sound_similarity", "span_phones",
    "to_feature_vectors", "weighted_levenshtein",
]
