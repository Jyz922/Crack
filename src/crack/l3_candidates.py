"""L3: deterministic, AGE-FREE ambiguity-candidate ranking over L2 senses.

aoa_estimate is never read here (README deviation 1: age effects live in L7).

Every retrieved WordNet sense remains a lexical proposal; there is no frequency
gate. Dictionary multiplicity is not evidence of two meanings in this text.

score = W_CONTRAST * contrast + W_BALANCE * balance
  contrast (strong)  1.0 if two senses carry different WordNet lexname()s, else 0.
  balance  (weak)    (c2 + 1) / (c1 + 1), the existing smoothed search heuristic.
                     balance_observed marks whether any counts were observed:
                     0/0 is unknown, not evidence of balanced usage. Alternative
                     ranking rules require validation on independent data.
Contrast outweighs balance, so every contrastive term ranks above every
non-contrastive one.

Compound splits (source "wordnet_split:a+b"): contrast = a part's top lexname
differs from the whole word's; balance is between the two parts' top counts.

Multiword expressions (source "wordnet_mwe:<lemma>"): the idiomatic reading
(MWE senses) vs the literal readings of its content words. contrast = some
word's top lexname differs from the MWE's; balance is between the MWE's top
count and that word's.

Soundalikes (workstream 03, from L2Result.soundalikes): contrast = the
surface word's top lexname differs from the best alternate's (a coinage with
no senses of its own, such as "purr-suing", counts as contrastive); balance is
between the two top counts. They use a SEPARATE budget: a soundalike term that
already holds a homograph slot just gains its alternates, and the others are
appended after the homograph top-k, so the homograph shortlist never changes.
"""

from __future__ import annotations

from collections import defaultdict

from .schema import CandidateEntry, L3Result, SenseEntry, SoundalikeCandidate

W_CONTRAST = 0.7
W_BALANCE = 0.3


def _count(s: SenseEntry) -> int:
    return s.semcor_count or 0


def _top(senses: list[SenseEntry]) -> SenseEntry:
    # max() keeps the first of equal counts, i.e. WordNet's own sense order.
    return max(senses, key=_count)


def _entry(
    term: str,
    contrast: bool,
    c1: int,
    c2: int,
    split: bool,
    sense_a_id: str | None = None,
    sense_b_id: str | None = None,
) -> CandidateEntry:
    observed = max(c1, c2) > 0
    balance = (c2 + 1) / (c1 + 1) if contrast else 0.0
    return CandidateEntry(
        term=term,
        score=round(W_CONTRAST * contrast + W_BALANCE * balance, 4),
        score_components={
            "contrast": float(contrast), "balance": round(balance, 4),
            "top_count": float(c1), "contrast_count": float(c2),
            "compound_split": float(split),
            "balance_observed": float(observed),
        },
        sense_a_id=sense_a_id,
        sense_b_id=sense_b_id,
    )


def _homograph(term: str, whole: list[SenseEntry]) -> CandidateEntry:
    top = _top(whole)
    others = [s for s in whole if s.lexname != top.lexname]
    if not others:
        return _entry(term, False, _count(top), 0, split=False, sense_a_id=top.sense_id)
    top_other = _top(others)
    return _entry(
        term, True, _count(top), _count(top_other), split=False,
        sense_a_id=top.sense_id, sense_b_id=top_other.sense_id,
    )


def _split(term: str, source: str, whole: list[SenseEntry], parts: list[SenseEntry]) -> CandidateEntry | None:
    if not whole:
        return None
    tops = []
    # ponytail: a part-sense belongs to part p iff its lemma is p; a part WordNet
    # only knows by an inflected form ("pets") is dropped rather than guessed.
    for p in source.split(":", 1)[1].split("+"):
        mine = [s for s in parts if s.lemma.lower() == p]
        if not mine:
            return None
        tops.append(_top(mine))
    whole_top = _top(whole)
    contrast_parts = [t for t in tops if t.lexname != whole_top.lexname]
    contrast = bool(contrast_parts)
    c1, c2 = sorted((_count(t) for t in tops), reverse=True)
    other_sense_id = contrast_parts[0].sense_id if contrast_parts else tops[0].sense_id
    candidate = _entry(
        term, contrast, c1, c2, split=True,
        sense_a_id=whole_top.sense_id, sense_b_id=other_sense_id,
    )
    candidate.split_options = [tuple(source.split(":", 1)[1].split("+"))]
    return candidate


def _mwe(phrase: str, mwe: list[SenseEntry], whole: dict[str, list[SenseEntry]]) -> CandidateEntry | None:
    words = [whole[w] for w in phrase.split() if w in whole]
    if not words:
        return None
    top = _top(mwe)
    literal = [_top(ss) for ss in words]
    contrasting = [t for t in literal if t.lexname != top.lexname]
    other = _top(contrasting) if contrasting else _top(literal)
    c1, c2 = sorted((_count(top), _count(other)), reverse=True)
    return _entry(
        phrase, bool(contrasting), c1, c2, split=False,
        sense_a_id=top.sense_id, sense_b_id=other.sense_id,
    )


def _soundalike(
    term: str, surface: list[SenseEntry], alt_senses: list[SenseEntry], cand: SoundalikeCandidate,
) -> CandidateEntry | None:
    best = cand.alternates[0]
    mine = [s for s in alt_senses if s.source == f"soundalike:{best.form}"]
    if not mine:
        return None
    alt_top = _top(mine)
    surface_top = _top(surface) if surface else None
    contrast = surface_top is None or surface_top.lexname != alt_top.lexname
    c1, c2 = sorted((_count(alt_top), _count(surface_top) if surface_top else 0), reverse=True)
    entry = _entry(term, contrast, c1, c2, split=False,
                   sense_a_id=surface_top.sense_id if surface_top else None, sense_b_id=alt_top.sense_id)
    _mark_soundalike(entry, cand)
    return entry


def _mark_soundalike(entry: CandidateEntry, cand: SoundalikeCandidate) -> None:
    entry.soundalike_alternates = list(cand.alternates)
    entry.score_components.update({
        "soundalike": 1.0,
        "phonetic_sim": cand.alternates[0].sim,
        "phonetic_sim_cal": cand.alternates[0].sim_cal,
    })


def rank(
    senses: list[SenseEntry],
    top_k: int,
    preferred_term: str | None = None,
    soundalikes: list[SoundalikeCandidate] | None = None,
    soundalike_top_k: int = 0,
) -> L3Result:
    whole: dict[str, list[SenseEntry]] = defaultdict(list)
    splits: dict[tuple[str, str], list[SenseEntry]] = defaultdict(list)
    mwes: dict[str, list[SenseEntry]] = defaultdict(list)
    alt_senses: dict[str, list[SenseEntry]] = defaultdict(list)
    for s in senses:
        if s.source.startswith("soundalike:"):
            alt_senses[s.term].append(s)
            continue
        if s.source == "wordnet":
            whole[s.term].append(s)
        elif s.source.startswith("wordnet_mwe:"):
            mwes[s.term].append(s)
        else:
            splits[(s.term, s.source)].append(s)
    cands = [_homograph(t, ss) for t, ss in whole.items()]
    cands += [c for (t, src), ss in splits.items() if (c := _split(t, src, whole[t], ss))]
    cands += [c for t, ss in mwes.items() if (c := _mwe(t, ss, whole))]
    cands.sort(key=lambda c: (-c.score, c.term))
    # One slot per term, retaining every supported split proposal. A ranking
    # score sets search order; it must not erase an alternative mechanism.
    best: dict[str, CandidateEntry] = {}
    for c in cands:
        if c.term not in best:
            best[c.term] = c
        else:
            retained = best[c.term]
            retained.split_options = list(dict.fromkeys(retained.split_options + c.split_options))
            if c.split_options:
                retained.score_components["compound_split"] = 1.0
    ranked = list(best.values())
    if preferred_term:
        norm = preferred_term.lower()
        if norm in best:
            ranked = [best[norm]] + [c for c in ranked if c.term != norm]
    shortlist, deferred = ranked[:top_k], ranked[top_k:]
    extras = _soundalike_extras(shortlist, deferred, whole, alt_senses, soundalikes or [], soundalike_top_k)
    return L3Result(
        candidates=shortlist + extras,
        deferred_candidates=[c for c in deferred if c not in extras],
        total_terms=len(ranked) + sum(1 for c in extras if c.term not in best),
    )


def _soundalike_extras(
    shortlist: list[CandidateEntry], deferred: list[CandidateEntry],
    whole: dict[str, list[SenseEntry]], alt_senses: dict[str, list[SenseEntry]],
    soundalikes: list[SoundalikeCandidate], budget: int,
) -> list[CandidateEntry]:
    """Separate soundalike budget; never reorders or replaces homograph slots."""
    if budget <= 0:
        return []
    in_shortlist = {c.term: c for c in shortlist}
    in_deferred = {c.term: c for c in deferred}
    extras: list[CandidateEntry] = []
    for cand in sorted(soundalikes, key=lambda c: (-c.alternates[0].sim_cal, c.char_span)):
        term = cand.surface.lower()
        if term in in_shortlist:
            _mark_soundalike(in_shortlist[term], cand)  # same slot, extra reading
            continue
        if len(extras) >= budget:
            continue
        if term in in_deferred:
            entry = in_deferred[term]
            _mark_soundalike(entry, cand)
        else:
            entry = _soundalike(term, whole.get(term, []), alt_senses.get(term, []), cand)
        if entry is not None:
            extras.append(entry)
    return extras
