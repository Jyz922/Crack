"""P0 pronunciation lexicon: words and spans to ARPAbet phones and feature vectors.

Source: the CMU Pronouncing Dictionary as distributed with NLTK
(``nltk.corpus.cmudict``, data id ``"cmudict"``, revision 0.7a). The PyPI
``cmudict`` package is deliberately not used: it is GPL-3.0-or-later and CRACK
is MIT. The corpus is downloaded to ``data/nltk_data`` on first use, the same
way ``l2_senses.wordnet`` handles WordNet. Offline tests block the network, so
that directory must be populated before the test suite runs.

Pronunciations are American English only. Lexical stress is stripped, except
that unstressed AH0 and ER0 are kept distinct because they map to the reduced
vowels ə and ɚ.
"""
from __future__ import annotations

import itertools
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Literal

import nltk

from crack.phonetics.features import has_segment, segment_vector

NLTK_DIR = Path(__file__).resolve().parents[3] / "data" / "nltk_data"
MAX_PRONUNCIATION_COMBOS = 16

# One ARPAbet phone -> the IPA segment(s) PanPhon has a row for.
# Diphthongs and affricates are two segments, matching how PanPhon segments
# the IPA strings the reference script builds (aɪ -> a + ɪ, tʃ -> t + ʃ), so
# lengths and scores agree with docs/soundalike/reference_wlev_fixed.py.
# ER uses the r-coloured vowels ɜ˞ / ə˞, the PanPhon spellings of ɝ / ɚ.
# (The reference maps ER to ɝ, which PanPhon silently drops.)
ARPA_TO_IPA: dict[str, tuple[str, ...]] = {
    "AA": ("ɑ",), "AE": ("æ",), "AH": ("ʌ",), "AH0": ("ə",), "AO": ("ɔ",),
    "AW": ("a", "ʊ"), "AY": ("a", "ɪ"), "EH": ("ɛ",), "ER": ("ɜ˞",), "ER0": ("ə˞",),
    "EY": ("e", "ɪ"), "IH": ("ɪ",), "IY": ("i",), "OW": ("o", "ʊ"), "OY": ("ɔ", "ɪ"),
    "UH": ("ʊ",), "UW": ("u",),
    "B": ("b",), "CH": ("t", "ʃ"), "D": ("d",), "DH": ("ð",), "F": ("f",),
    "G": ("ɡ",), "HH": ("h",), "JH": ("d", "ʒ"), "K": ("k",), "L": ("l",),
    "M": ("m",), "N": ("n",), "NG": ("ŋ",), "P": ("p",), "R": ("ɹ",),
    "S": ("s",), "SH": ("ʃ",), "T": ("t",), "TH": ("θ",), "V": ("v",),
    "W": ("w",), "Y": ("j",), "Z": ("z",), "ZH": ("ʒ",),
}
_missing = [seg for segs in ARPA_TO_IPA.values() for seg in segs if not has_segment(seg)]
if _missing:  # fail loudly instead of silently dropping phones
    raise RuntimeError(f"PanPhon has no feature row for IPA segments: {_missing}")

_CMU_LOCK = threading.Lock()
_EDGE_PUNCT = re.compile(r"^[^\w']+|[^\w']+$")


@lru_cache(maxsize=1)
def _cmu() -> dict[str, list[list[str]]]:
    with _CMU_LOCK:
        if str(NLTK_DIR) not in nltk.data.path:
            nltk.data.path.insert(0, str(NLTK_DIR))
        try:
            nltk.data.find("corpora/cmudict")
        except LookupError:
            try:
                nltk.download("cmudict", download_dir=str(NLTK_DIR), quiet=True, raise_on_error=True)
            except Exception as exc:  # offline test runs block the network
                raise LookupError(
                    f"CMUdict corpus missing from {NLTK_DIR}. Fetch it once with: "
                    "py -3.11 -c \"import nltk; nltk.download('cmudict', download_dir='data/nltk_data')\""
                ) from exc
        from nltk.corpus import cmudict

        return cmudict.dict()


def _strip_stress(phone: str) -> str:
    if phone in ("AH0", "ER0"):
        return phone
    return phone.rstrip("012")


def _single_word(word: str) -> list[tuple[str, ...]]:
    entries = _cmu().get(word.lower(), [])
    seen: dict[tuple[str, ...], None] = {}
    for entry in entries:
        seen.setdefault(tuple(_strip_stress(p) for p in entry), None)
    return list(seen)


def _combine(parts: list[list[tuple[str, ...]]]) -> list[tuple[str, ...]]:
    if not parts or any(not p for p in parts):
        return []
    combos = itertools.islice(itertools.product(*parts), MAX_PRONUNCIATION_COMBOS)
    seen: dict[tuple[str, ...], None] = {}
    for combo in combos:
        seen.setdefault(tuple(itertools.chain.from_iterable(combo)), None)
    return list(seen)


def pronunciations(word: str) -> list[tuple[str, ...]]:
    """All CMUdict pronunciations of one written word, stress stripped.

    A hyphenated coinage such as "purr-suing" is looked up whole first, then as
    the concatenation of its parts. Returns [] when any part is missing.
    """
    cleaned = _EDGE_PUNCT.sub("", word.strip())
    if not cleaned:
        return []
    whole = _single_word(cleaned)
    if whole or "-" not in cleaned:
        return whole
    return _combine([_single_word(part) for part in cleaned.split("-") if part])


def span_phones(tokens: list[str]) -> list[tuple[str, ...]]:
    """Pronunciations of a 1-3 token span, concatenated across tokens."""
    if not 1 <= len(tokens) <= 3:
        raise ValueError("span_phones expects 1-3 tokens")
    return _combine([pronunciations(token) for token in tokens])


def lookup_source(word: str) -> Literal["cmudict", "missing"]:
    """Where a pronunciation came from. g2p_en is not adopted (see handoff 01)."""
    return "cmudict" if pronunciations(word) else "missing"


def to_ipa_segments(arpabet: tuple[str, ...]) -> list[str]:
    try:
        return [seg for phone in arpabet for seg in ARPA_TO_IPA[phone]]
    except KeyError as exc:
        raise KeyError(f"Unknown ARPAbet phone {exc.args[0]!r}") from None


def to_feature_vectors(arpabet: tuple[str, ...]) -> list[tuple[int, ...]]:
    """One PanPhon feature vector per IPA segment (diphthongs give two)."""
    return [segment_vector(seg) for seg in to_ipa_segments(arpabet)]
