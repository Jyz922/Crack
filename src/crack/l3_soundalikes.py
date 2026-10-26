"""P2 soundalike finder: utterances in the text that sound like another word.

Recall stage only. It reports candidates with graded phonetic scores and never
decides that something is wordplay; L4 anchors both readings and L5/L6 judge
resolution. Retrieval paths covered here:

- sound_pair: two content words in the same text that sound alike
  (drum/drama, cat/cad, cat/cash). The surface is the later word and the
  alternate is the earlier one. A pair is kept when its raw similarity reaches
  the configured percentile of random same-length CMUdict pairs; a fixed raw
  threshold such as 0.75 sits at the random-pair mean and floods the output.
- sound_substitution via hyphen merge: a hyphenated coinage whose combined
  pronunciation is exactly an existing word ("purr-suing" -> "pursuing").
  Exact phone match only (k = 0); near matches are workstream 05.
- sound_substitution via lexicon: each content word queries the reverse
  pronunciation index for exact homophones absent from the text. OEWN must
  supply a sense for the alternate. No near-neighbor search is performed.

The joined spelling of a hyphen group ("cat-nap" -> "catnap") is not a
soundalike: it is handled as resegmentation by L2/L3.
"""
from __future__ import annotations

import itertools
import os
import re
from collections import defaultdict
from functools import lru_cache

from .config import Settings
from .l2_senses import STOPWORDS, _wordnet_locked, wordnet
from .phonetics import MissingPronunciation, pronunciations, sound_similarity
from .phonetics.calibration import percentile_value
from .phonetics.lexicon import _cmu
from .schema import Alternate, L1Result, SoundalikeCandidate

_WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")


def _norm(word: str) -> str:
    return re.sub(r"['’]s?$", "", word.lower())


def _content_spans(text: str) -> list[tuple[str, tuple[int, int]]]:
    """First occurrence of each content word, with its character span."""
    seen: dict[str, tuple[int, int]] = {}
    for m in _WORD.finditer(text):
        word = _norm(m.group())
        if word.isalpha() and word not in STOPWORDS and word not in seen:
            seen[word] = (m.start(), m.start() + len(word))
    return list(seen.items())


def _key(phones: tuple[str, ...]) -> tuple[str, ...]:
    """Lookup key with every stress mark removed (ER0 -> ER, AH0 -> AH)."""
    return tuple(p.rstrip("012") for p in phones)


@lru_cache(maxsize=1)
def _reverse_index() -> dict[tuple[str, ...], tuple[str, ...]]:
    index: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for word, entries in _cmu().items():
        if word.isalpha():
            for entry in entries:
                index[_key(tuple(entry))].append(word)
    return {k: tuple(sorted(set(v))) for k, v in index.items()}


@lru_cache(maxsize=8192)
def _in_wordnet(word: str) -> bool:
    """Lexical validity filter: keep alternates OEWN can give senses for."""
    wn = wordnet()
    return bool(wn.synsets(word))


def _bases(word: str) -> set[str]:
    wn = wordnet()
    return {word} | {b for pos in "nvar" if (b := wn.morphy(word, pos))}


def _same_family(a: str, b: str) -> bool:
    """Inflections and derivations (camp/camper, bring/brought, prescribe/
    prescription) share a stem, not just a sound: skip them as pairs."""
    if _bases(a) & _bases(b):
        return True
    shared = len(os.path.commonprefix([a, b]))
    return shared >= 4 or (shared >= 3 and shared == min(len(a), len(b)))


def _alternate(surface: str, form: str, source: str) -> Alternate | None:
    try:
        score = sound_similarity(surface, form)
    except MissingPronunciation:
        return None
    return Alternate(
        form=form, phones=list(score.pron_pair[1]),
        sim=round(score.sim, 4), sim_cal=round(score.sim_cal, 4), source=source,
    )


def _in_text_pairs(text: str, percentile: str) -> list[SoundalikeCandidate]:
    by_surface: dict[str, tuple[tuple[int, int], list[Alternate]]] = {}
    words = _content_spans(text)
    for (early, _), (late, late_span) in itertools.combinations(words, 2):
        if _same_family(early, late):
            continue
        try:
            score = sound_similarity(late, early)
        except MissingPronunciation:
            continue
        if score.sim < percentile_value(score.length, percentile):
            continue
        alt = Alternate(
            form=early, phones=list(score.pron_pair[1]),
            sim=round(score.sim, 4), sim_cal=round(score.sim_cal, 4), source="in_text",
        )
        by_surface.setdefault(late, (late_span, []))[1].append(alt)
    return [
        SoundalikeCandidate(
            surface=text[span[0]:span[1]], char_span=span,
            mechanism="sound_pair", alternates=alts,
        )
        for surface, (span, alts) in by_surface.items()
    ]


def _hyphen_merges(l1: L1Result, text: str) -> list[SoundalikeCandidate]:
    out = []
    for group in l1.hyphen_groups:
        start = text.find(group)
        if start < 0:
            continue
        joined = group.replace("-", "").lower()
        forms: dict[str, None] = {}
        for pron in pronunciations(group):
            for form in _reverse_index().get(_key(pron), ()):
                if form != joined and _in_wordnet(form):
                    forms.setdefault(form, None)
        alts = [a for f in forms if (a := _alternate(group, f, "hyphen_merge"))]
        if alts:
            out.append(SoundalikeCandidate(
                surface=group, char_span=(start, start + len(group)),
                mechanism="sound_substitution", alternates=alts,
            ))
    return out


def _word_homophones(text: str, max_alternates: int) -> list[SoundalikeCandidate]:
    """Exact dictionary homophones only; no gold targets or curated pair list."""
    present = {_norm(m.group()) for m in _WORD.finditer(text)}
    out = []
    for word, span in _content_spans(text):
        prons = set(pronunciations(word))
        forms = set()
        for pron in prons:
            for form in _reverse_index().get(_key(pron), ()):
                # Exact homophones can share a long spelling prefix while
                # being different lexemes. Only exclude shared inflectional
                # bases here; the near-pair prefix heuristic is too broad.
                if form in present or form in STOPWORDS or _bases(word) & _bases(form):
                    continue
                # The shared reverse index removes all stress digits. The
                # scorer preserves AH0/ER0 reduction, so require phone identity
                # under that same normalization before accepting a homophone.
                if prons.isdisjoint(pronunciations(form)) or not _in_wordnet(form):
                    continue
                forms.add(form)
        alts = [a for form in sorted(forms)[:max_alternates]
                if (a := _alternate(word, form, "lexicon"))]
        if alts:
            out.append(SoundalikeCandidate(
                surface=text[slice(*span)], char_span=span,
                mechanism="sound_substitution", alternates=alts,
            ))
    return out


@_wordnet_locked
def find_soundalikes(l1: L1Result, text: str, settings: Settings) -> list[SoundalikeCandidate]:
    """Soundalike candidates in *text* (the L0-normalised text L4 quotes from)."""
    if settings.SOUNDALIKE_MAX_CANDIDATES == 0:
        return []
    retrieved = (_hyphen_merges(l1, text)
                 + _in_text_pairs(text, settings.PHONETIC_RETRIEVE_PERCENTILE)
                 + _word_homophones(text, settings.SOUNDALIKE_MAX_ALTERNATES))
    # A surface can have both an in-text pair and an absent homophone. Share
    # one candidate slot; each alternate retains its own relation via source.
    merged: dict[tuple[int, int], SoundalikeCandidate] = {}
    for cand in retrieved:
        if cand.char_span not in merged:
            merged[cand.char_span] = cand
        else:
            existing = merged[cand.char_span]
            known = {a.form for a in existing.alternates}
            existing.alternates.extend(a for a in cand.alternates if a.form not in known)
    cands = list(merged.values())
    for cand in cands:
        cand.alternates.sort(key=lambda a: (-a.sim_cal, a.form))
        del cand.alternates[settings.SOUNDALIKE_MAX_ALTERNATES:]
    cands.sort(key=lambda c: (-c.alternates[0].sim_cal, c.char_span))
    return cands[:settings.SOUNDALIKE_MAX_CANDIDATES]
