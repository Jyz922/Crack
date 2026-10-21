"""P1 sound similarity: graded (non-binary) phone distance and word similarity.

Formulas (docs/soundalike/design.md, "Formulas"):

    δ(a, b) = Σ_f w_f · |a_f − b_f| / (2 · Σ_f w_f)          in [0, 1]

where a_f, b_f ∈ {−1, 0, +1} are PanPhon feature values and w_f are PanPhon's
feature weights matched by name (Σ_f w_f = 7.25). A one-feature voicing change
(t/d) costs 0.0172; a place-and-manner change (t/ʃ) costs 0.1379.

    D[i][0] = indel · i,   D[0][j] = indel · j
    D[i][j] = min(D[i−1][j] + indel, D[i][j−1] + indel, D[i−1][j−1] + δ(p_i, q_j))
    sim     = 1 − D[n][m] / max(n, m)

with indel = 0.5 by default. ``sim_cal`` rescales ``sim`` against random-pair
baselines; see ``calibration.py``.
"""
from __future__ import annotations

from dataclasses import dataclass

from crack.phonetics.calibration import calibrate
from crack.phonetics.features import feature_weights, weight_vector
from crack.phonetics.lexicon import pronunciations, span_phones, to_feature_vectors

DEFAULT_INDEL = 0.5

# Name-aligned weights (the documented fix for panphon's positional zip).
FEATURE_WEIGHTS: dict[str, float] = feature_weights()
_W = weight_vector()
_W_SUM = sum(_W)


class MissingPronunciation(LookupError):
    """No CMUdict pronunciation for a word or span."""


def phone_distance(a, b) -> float:
    """δ in [0, 1] between two feature vectors."""
    return sum(w * abs(x - y) for w, x, y in zip(_W, a, b)) / (2 * _W_SUM)


def weighted_levenshtein(p, q, indel: float = DEFAULT_INDEL):
    """Edit distance over feature-vector sequences, with the alignment.

    Returns (distance, alignment); the alignment is a tuple of (i, j) index
    pairs where None marks an insertion or deletion.
    """
    n, m = len(p), len(q)
    d = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        d[i][0] = i * indel
    for j in range(1, m + 1):
        d[0][j] = j * indel
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(
                d[i - 1][j] + indel,
                d[i][j - 1] + indel,
                d[i - 1][j - 1] + phone_distance(p[i - 1], q[j - 1]),
            )
    alignment = []
    i, j = n, m
    while i or j:  # deterministic backtrace: substitution, then deletion, then insertion
        if i and j and d[i][j] == d[i - 1][j - 1] + phone_distance(p[i - 1], q[j - 1]):
            alignment.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + indel:
            alignment.append((i - 1, None))
            i -= 1
        else:
            alignment.append((None, j - 1))
            j -= 1
    return d[n][m], tuple(reversed(alignment))


@dataclass(frozen=True)
class SoundScore:
    sim: float
    sim_cal: float
    distance: float
    pron_pair: tuple[tuple[str, ...], tuple[str, ...]]
    alignment: tuple[tuple[int | None, int | None], ...]
    length: int  # max(n, m) in IPA segments; the calibration bucket


def _prons(utterance: str | list[str]) -> list[tuple[str, ...]]:
    tokens = utterance.split() if isinstance(utterance, str) else list(utterance)
    prons = pronunciations(tokens[0]) if len(tokens) == 1 else span_phones(tokens)
    if not prons:
        raise MissingPronunciation(f"No CMUdict pronunciation for {utterance!r}")
    return prons


def score_pronunciations(a: tuple[str, ...], b: tuple[str, ...], indel: float = DEFAULT_INDEL) -> SoundScore:
    p, q = to_feature_vectors(a), to_feature_vectors(b)
    distance, alignment = weighted_levenshtein(p, q, indel)
    length = max(len(p), len(q), 1)
    sim = 1 - distance / length
    return SoundScore(sim, calibrate(sim, length), distance, (a, b), alignment, length)


def sound_similarity(x: str | list[str], y: str | list[str], indel: float = DEFAULT_INDEL) -> SoundScore:
    """Similarity of two words or 1-3 word spans: the best pronunciation pair.

    Raises MissingPronunciation when either side has no CMUdict entry.
    """
    best: SoundScore | None = None
    for a in _prons(x):
        for b in _prons(y):
            score = score_pronunciations(a, b, indel)
            if best is None or score.sim > best.sim:
                best = score
    assert best is not None
    return best
