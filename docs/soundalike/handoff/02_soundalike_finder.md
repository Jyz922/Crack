# 02 — Soundalike finder (in-text pairs + hyphen merge/split)
Last updated: 2026-10-19 by soundalike docs-planning session (offline, no code written)

Status: **not started**. Back to [HANDOFF](../HANDOFF.md).

## Checks this session

| Check | Command | Result |
|---|---|---|
| Current L1 tokens for the hyphenated texts | `_TOKEN.findall(...)` from `l1_surface.py` | `purr`,`suing` and `cat`,`nap`: hyphen forms are lost |
| WordNet lemma `catnap` | `wordnet().synsets("catnap")` | `nap.n.04`, `nap.v.01` (exists) |
| `compound_splits("catnap")` | `py -3.11 -c ...` | `[('cat', 'nap')]` |
| Existing L4 validation on a hyphen split | `validate_l4_response`, term `catnap` / `cat-nap` | **Both rejected** (quote/term mismatch; joined parts ≠ `cat-nap`) |
| Finder behaviour on the three texts | none | **NOT run**; design.md's values are expectations from a scratch environment |

## Goal

Implement the narrowest soundalike finder (instructor component (a)) that covers
all three test texts:

- (i) pairs of content words within the text (drum/drama, cat/cad, cat/cash);
- (iii) hyphen merge/split ("purr-suing" ↔ *pursuing*; "cat-nap" → cat + nap).

It also makes hyphenated spans visible to L1/L2. Lexicon neighbours (ii) are
[05](05_lexicon_neighbours.md); DP resegmentation (iv) and the curated list (v)
are [06](06_optional_extensions.md).

## Files to create/modify

- `src/crack/l1_surface.py`: add a second regex pass
  `[A-Za-z]+(?:-[A-Za-z]+)+` over the raw text and store the matches in
  `hyphen_groups`. **Do not change `_TOKEN` or `tokens`.**
- `src/crack/schema.py`: add `L1Result.hyphen_groups: list[str] = []`. The
  existing, never-populated `L1Result.compound_splits` field is unrelated; do
  not reuse it. Also add the `Alternate` and `SoundalikeCandidate` models,
  because `find_soundalikes` returns them. design.md lists these under the
  contract stage; they are needed here first, and [03](03_contract_l3_l4_l0post.md)
  adds the remaining fields.
- Create `src/crack/l3_soundalikes.py`: `find_soundalikes`.
- `src/crack/l2_senses.py` `retrieve`: for each hyphen group, add whole-word
  senses for the joined form (`senses_for("catnap", term=<term>)`) **and** its
  `compound_splits` part-senses. Without whole-word senses, `l3_candidates._split`
  returns `None` (`if not whole`).
- `src/crack/layers.py` `run_l2`: call `find_soundalikes` and append
  `senses_for(alt.form, term=surface, source=f"soundalike:{alt.form}")` for each
  alternate, plus AoA for alternates.
- Where the `SoundalikeCandidate` list is stored on the record: `L2Result` has
  only `senses` and is `extra="forbid"`. Add a field, or recompute in L3 (open
  decision).
- `tests/test_l1.py`, `tests/test_l2.py`, plus a new `tests/test_soundalike_finder.py`.

## Interfaces

```python
# src/crack/schema.py
class Alternate(BaseModel):            # extra="forbid"
    form: str                          # spelled as ordinary words, e.g. "pursuing", "let us"
    phones: list[str]
    sim: float; sim_cal: float
    source: Literal["in_text", "lexicon", "hyphen_merge", "resegmentation", "curated_list", "llm_verified"]

class SoundalikeCandidate(BaseModel):  # extra="forbid"
    surface: str                       # exact source substring, e.g. "purr-suing"
    char_span: tuple[int, int]         # text[span[0]:span[1]] == surface
    mechanism: Literal["sound_pair", "sound_substitution"]
    alternates: list[Alternate]        # top 3 by sim_cal, after the frequency floor

# src/crack/l3_soundalikes.py
def find_soundalikes(l1: L1Result, text: str, settings: Settings) -> list[SoundalikeCandidate]
```

- In-text pairs: content tokens only (reuse `l2_senses.STOPWORDS`), scored with
  01's `sound_similarity`, kept at raw sim ≥ `PHONETIC_TAU_RETRIEVE`,
  `mechanism="sound_pair"`.
- Hyphen merge: concatenate the parts' phones and look up words with the same
  stress-stripped phone sequence. design.md doesn't specify this lookup. The
  minimal form is a reverse CMUdict index on exact phones (k = 0), which is a
  subset of 05's deletion index. `mechanism="sound_substitution"`,
  `source="hyphen_merge"`.
- Hyphen split: the joined form goes through the existing `compound_splits`
  (resegmentation path, no phonetics).

## Acceptance tests

Offline, with the provider monkeypatched to raise. Phonetic values are pinned to
01's observed outputs; the numbers below are design.md's expectations.

1. `analyze(t2).hyphen_groups == ["purr-suing"]`;
   `analyze(t3).hyphen_groups == ["cat-nap"]`; text 1 → `[]`.
2. `analyze(x).tokens` is unchanged for every item in
   `corpus/joke_corpus_blind.jsonl` and `tests/fixtures/*.jsonl` (snapshot the
   current tokens before the change).
3. Text 2: a candidate with `surface == "purr-suing"`, `text[slice(*char_span)] == surface`,
   and alternate `pursuing` with `source="hyphen_merge"` at sim 1.000 (stress
   stripped: purr P ER1 + suing S UW1 IH0 NG = pursuing P ER0 S UW1 IH0 NG).
   An in-text pair cat/cad with sim ≈ 0.994.
4. Text 1: in-text pair drum/drama, `sound_pair`, sim ≈ 0.890.
5. Text 3: in-text pair cat/cash, sim ≈ 0.954. L2 senses include whole-word
   `catnap` senses and `wordnet_split:cat+nap` part-senses under the chosen
   term spelling. `l3_candidates.rank` produces a split candidate for it.
6. Hard-negative behaviour: the finder reports cat/cad but does not drop or
   promote it. Selection is L4's job.
7. The full existing offline suite still passes.
8. Text 3 ("...turn her cat-nap into cash.") produces a **validated L4
   candidate** for `cat-nap`: L3 offers it, and a mocked L4 PASS
   `resegmentation` response with parts `["cat", "nap"]` passes
   `validate_l4_response`. Today this fails on two counts: the hyphenated form
   fails L4 quote validation, and L2 adds no whole-word senses for `catnap`.
   The validation half lands in [03](03_contract_l3_l4_l0post.md) (its test 6);
   this workstream is not done until both halves pass.

## Depends on

[01](01_phonetic_core.md) (`sound_similarity`, `pronunciations`).

## Open decisions

- **Term spelling for hyphen splits**: keep the exact surface `cat-nap` (so
  quotes stay verbatim) and have 03 compare `"".join(split_parts)` against the
  term with hyphens removed (recommended), or use `catnap` and relax the
  quote rule. Either way, `validate_l4_response` must change in 03.
- Where finder output is stored (`L2Result` field vs recompute in L3).
- τ_retrieve (team table: start at raw ≥ 0.75, then fit).
- Whether lexicalised hyphen compounds ("well-known") should be skipped.

## Risks

- **Homograph regression.** Hyphen groups add new split candidates and
  alternates add senses, which can change L3's top 8 for existing corpus items
  and move the README's October 4 project-corpus numbers. Measure on the
  60-item corpus (live run, NOT run here).
- Over-detection: identical homophones with no contextual support (band/banned)
  will be found. The finder is a recall stage only.
- `char_span` must index the L0-pre-normalised text that L4 quotes against, not
  the raw input.
- Curly apostrophes and contractions ("wasn't") inside hyphen groups.
