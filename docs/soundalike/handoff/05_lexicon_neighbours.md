# 05 — Lexicon neighbours (k ≤ 2 phone deletion index + frequency floor)
Last updated: 2026-10-19 by soundalike docs-planning session (offline, no code written)

Status: **not started**. Back to [HANDOFF](../HANDOFF.md).

## Checks this session

| Check | Command | Result |
|---|---|---|
| Word-frequency package | `py -3.11 -c "import wordfreq"` | **Missing** (and no frequency dependency in `pyproject.toml`) |
| Index size / build time (114,160 prons, 696,752 keys at k = 1, 1.5 s) | none | **NOT run**; from design.md (notes' run) |
| k = 2 build time | none | **NOT run**; design.md says "tens of seconds", not measured |
| knight has 34 neighbours at distance 1 | none | **NOT run**; from design.md |

## Goal

Retrieve soundalike targets that do not occur in the text: lexicon finder
path (ii). This covers cases like catnap ↔ *kidnap* and drum ↔ *drama* without
drama in the text, both of which are phone distance 2 and so missed at k = 1.
Neighbours are **unverified proposals**; the caller scores each one with 01's
`sound_similarity`.

## Files to create/modify

- Create `src/crack/phonetics/index.py`.
- Modify `src/crack/l3_soundalikes.py` (from [02](02_soundalike_finder.md)) to
  union lexicon neighbours into each candidate's alternates (`source="lexicon"`).
- Modify `pyproject.toml`: a word-frequency dependency. `min_zipf` suggests the
  `wordfreq` package [Likely; design.md does not name it].
- Create `tests/test_phone_index.py`.

## Interfaces

```python
class PhoneDeletionIndex:
    @classmethod
    def build(cls, k: int = 2, min_zipf: float = 3.0) -> "PhoneDeletionIndex"
    def neighbours(self, phones: tuple[str, ...], k: int = 2) -> list[str]  # unverified
```

Keys are every stress-stripped CMUdict pronunciation with up to k phones
deleted. Query the same way and intersect, then apply the frequency floor
(`min_zipf`). Build once per process, lazily, behind a lock, as with
`l2_senses`' WordNet access.

## Acceptance tests

1. `neighbours(phones("catnap"), k=2)` contains `kidnap`, and `k=1` does not.
2. `neighbours(phones("drum"), k=2)` contains `drama`.
3. Every returned word that is re-scored with `sound_similarity` has edit
   distance ≤ k. Words below `min_zipf` are absent.
4. Deterministic order across two builds.
5. Build time and memory for k = 1 and k = 2 are measured on this machine and
   recorded in this file. Count of knight's distance-1 neighbours is recorded
   and compared with design.md's 34.
6. Mocked-pipeline regression: existing L3/L4 tests are unchanged with the
   index enabled (the soundalike budget is separate).

## Depends on

[01](01_phonetic_core.md) (pronunciations, similarity) and
[02](02_soundalike_finder.md) (finder to extend).

## Open decisions

- k (1 vs 2) and `min_zipf` value; fit on 04's Recall@k.
- Whether the index is built at import, at first use, or cached to disk
  (`data/` is gitignored).
- Cap on alternates per surface (design.md: top 3 by sim_cal; PunGraph found
  about 30 candidates add noise).

## Risks

- Over-detection: catnap ↔ kidnap is exactly the forced link LLMs accept.
  Rely on 03's validation and L5/L6, not on retrieval.
- k = 2 key explosion: memory and build time are unmeasured.
- Frequency-package licence and data size are unverified.
- Multi-word targets ("a ledge", "let us") are not reachable by a single-word
  index; see [06](06_optional_extensions.md) DP resegmentation.
