# 03 — Contract, L3 soundalike entries, L4, enums, L0-post, versions
Last updated: 2026-10-21 by soundalike-contract implementation session (offline; Linux VM, Windows check pending)

Status: **merged** (PR #7). Still open: a live 60-item corpus rerun after the L4 prompt change. Back to [HANDOFF](../HANDOFF.md).

## Checks this session

| Check | Command | Result |
|---|---|---|
| `RESPONSE_CONTRACT_VERSION` | read `src/crack/validation.py:11` | `"6"` |
| `CANDIDATE_SEARCH_VERSION` | read `src/crack/decisions.py:12` | `"4"` |
| Exact-key L4 contracts | read `schema.py`, `validation.py`, `l4_anchoring.py` | `L4Result` and `CandidateEntry` `extra="forbid"`; `L4_RESPONSE_FIELDS` (10 keys); `_L4LLMResponse` `extra="forbid"` |
| L4 prompt prohibition | read `prompts/l4_anchoring.md:32-36` | "do not invent prefix meanings or replace them with differently spelled soundalikes" |
| Who sets `OUT_OF_SCOPE_HOMOPHONE` | read `runner._l0_post_layer` | only when `record.final` already had that scope, i.e. nothing produces it |
| Resume version gate | read `runner.py:422-426` | reuses a record only if both versions equal the current constants |
| End-to-end, mocked L4/L5/L6 (real L0–L3) | `pytest tests/test_soundalike_end_to_end.py` | Text 2 → `VALID_SOUNDALIKE_JOKE`/`SOUNDALIKE`; text 1 → `VALID_SOUNDALIKE_JOKE` (sound_pair); text 3 → `VALID_COMPOUND_SPLIT_JOKE`; each with `per_age` and exactly one L4, L5 and L6 call. A forced alternate ("chasing") → `EXECUTION_FAILED` after one L4 call. Web result: `punchline` purr-suing, `alternate_form` pursuing |
| Contract and stage tests | `pytest tests/test_soundalike_contract.py` | 24 passed (11-key contract, verification, sound_pair, hyphen resegmentation, labels/versions, L3 budget, L4 prompt/shortlist, L5/L6 note, alternate AoA) |
| Homograph regression | 74 corpus + fixture texts, L1 tokens and L3 top-8 before/after, offline | **0 diffs** in terms, order, scores or sense ids (only new soundalike fields). 25 of 60 corpus texts show L4 an attached alternate and 8 get an appended soundalike candidate, so their L4 prompt changes |
| L5/L6 prompts for non-soundalike readings | rendered template vs `main` | **Byte-identical** (the note is empty); only the L4 prompt changed for homograph texts |
| Full offline suite (Linux) | `pytest -m "not live"` | 540 passed; the one mount-only timing failure passes on local disk |
| Full offline suite (Windows) | `py -3.11 -m pytest -m "not live" -q` | **NOT run** |
| Live 60-item corpus rerun after the L4 prompt change | `crack` live run | **NOT run** (paid); needed to confirm the October 4 homograph numbers |

## Implementation decisions (2026-10-21)

- **Free proposal + verify** (Daren): L4 may name an alternate the finder did
  not supply; it is accepted only at ≥ p99 random-pair similarity
  (`PHONETIC_VERIFY_PERCENTILE`). Finder-supplied alternates are accepted as
  is. Consequence: drum/drama (0.890) passes only because the finder supplies
  it (it is below p99).
- **drum/drama counts** as `sound_pair` (Daren), reported separately from
  `sound_substitution`.
- **Phonological age barrier deferred** (Daren): the age contract is
  unchanged; alternates are only added to the AoA lookup table.
- Separate L3 soundalike budget `L3_SOUNDALIKE_TOP_K = 4`; L4 keeps those
  extras beyond the homograph cut.
- `SOUNDALIKE` scope row sits after the homophone guard and before
  `HOMOGRAPH` (diagnostic only).
- `heterographic_homophone` moved from `EXCLUDED_MECHANISMS` to
  `ACCEPTED_MECHANISMS` (no code reads these sets).
- L5/L6 get the mechanism through a `{mechanism_note}` placeholder that is
  empty for non-soundalike readings, so those prompts are unchanged.
- `decisions.py` re-validation uses the default verification percentile (p99,
  equal to the setting's default); it has no settings object.

## Goal

Turn verified phonetic evidence into a first-class positive. L3 offers soundalike
entries, L4 may anchor a `sound_substitution` / `sound_pair` reading in the same
single request, local validation re-checks the alternate, and L0-post emits
`VALID_SOUNDALIKE_JOKE` with scope `SOUNDALIKE`. The contract versions are
bumped together.

## Files to create/modify

- `src/crack/enums.py`: `AnchorRelation.SOUND_SUBSTITUTION = "sound_substitution"`,
  `AnchorRelation.SOUND_PAIR = "sound_pair"`, `ScopeLabel.SOUNDALIKE`,
  `MainClassification.VALID_SOUNDALIKE_JOKE`; add the new label to the PUN set in
  `detection_status_for`.
- `src/crack/schema.py`: `CandidateEntry.soundalike_alternates: list[Alternate] = []`,
  `L4Result.alternate_form: str | None = None`. If the "phonological" age barrier
  is adopted, also `AgeEstimate.barrier` (an age-contract change; see below).
- `src/crack/validation.py`: add `alternate_form` to `L4_RESPONSE_FIELDS`; add
  the new checks; `RESPONSE_CONTRACT_VERSION = "7"`.
- `src/crack/decisions.py`: `CANDIDATE_SEARCH_VERSION = "5"`; `detection_decision`
  returns `VALID_SOUNDALIKE_JOKE` for `sound_*` relations, and its call to
  `validate_l4_response` (line 44) must pass the same alternates as L4 did.
- `src/crack/l3_candidates.py`: `_soundalike(...)` reusing `_entry`; a separate
  soundalike budget in `rank`.
- `src/crack/l4_anchoring.py`: add `alternate_form` to `_L4LLMResponse`.
  `_anchor_shortlist` adds each candidate's alternates (form, sim_cal,
  mechanism) and their senses to `candidate_details`.
- `src/crack/prompts/l4_anchoring.md`: a new "Soundalike assessment" section;
  11-key response; line 34's prohibition stays for compound splits and gains a
  pointer to the new section.
- `src/crack/l0_scope.py`: `LayerEvidence.has_soundalike`; a `SOUNDALIKE` row in
  `assign_scope_label`.
- `src/crack/runner.py`: `_l0_post_layer` sets `has_soundalike` and adds the label
  to the "decided" set and the per-age set (line 290); `format_analysis_report`
  verdict and description maps (lines 533, 546).
- `src/crack/serve.py:217` and `src/crack/static/index.html` (lines 1296, 1703,
  1726): the label sets hard-coded there.
- Required for an end-to-end positive (not in design.md's stage-3 list):
  L5/L6 prompt variables get a mechanism block (`l5_resolution.py`,
  `l6_distinctness.py`, prompts), and `age_evidence.age_inputs` adds
  `alternate_form` words to `aoa_lookup` so that L7 accepts their citations.
- `src/crack/config.py`: `PHONETIC_TAU_RETRIEVE`, `PHONETIC_TAU_VERIFY`,
  `SOUNDALIKE_MAX_CANDIDATES`, `PHONETIC_INDEL`; review `EXCLUDED_MECHANISMS`
  (it contains `heterographic_homophone`).
- When implemented: add the new status strings to `README.md`,
  `docs/response_validation.md` and `_README_STATUS_STRINGS` in
  `tests/test_enums.py`, together. `test_readme_links_complete_status_reference`
  requires every listed string to appear in `docs/response_validation.md`.
- Tests: `tests/test_l3.py`, `tests/test_l4.py`, `tests/test_l0.py`,
  `tests/test_runner.py`, `tests/test_enums.py`,
  `tests/test_response_contract_v3.py`.

## Interfaces

```python
# validation.py
def validate_l4_response(value, text, term, is_split, split_options=None,
                         alternates: list[Alternate] | None = None) -> dict
# PASS + sound_*: alternate_form nonempty AND (casefold-matches a supplied
#   alternate OR sound_similarity(term, alternate_form).sim_cal >= PHONETIC_TAU_VERIFY),
#   else ModelResponseError (no corrective request).
# sound_pair: term and alternate_form both occur in text.
# sound_*: the existing non-split rule applies (two different quotes, neither just the term).
# every other relation and every non-PASS status: alternate_form is None.

# l3_candidates.py
def _soundalike(term, surface_senses, alt_senses, alternates) -> CandidateEntry
# contrast = 1 if the surface's and the alternate's top lexnames differ; balance as in _entry;
# score_components += {"phonetic_sim", "phonetic_sim_cal", "soundalike": 1.0}; ties ordered by sim_cal.
```

Homograph scoring stays `0.7·contrast + 0.3·balance`, and ranking stays age-free.

Hyphen resegmentation (from [02](02_soundalike_finder.md)): the `RESEGMENTATION`
branch currently requires both quotes to equal the term and
`"".join(split_parts) == term`. That rejects `cat-nap` under either term
spelling. Change the comparison to ignore hyphens in the term, and keep quotes
verbatim.

## Acceptance tests

Offline only. Mock the provider in the style of `tests/test_l4.py`
(`SimpleNamespace` clients that record calls).

1. An 11-key L4 response is accepted; the old 10-key response is rejected
   (`missing=['alternate_form']`).
2. `sound_substitution` whose alternate is neither supplied nor ≥ τ_verify →
   `ModelResponseError`, with exactly one provider request recorded.
3. `sound_pair` whose alternate is absent from the text → rejected.
4. `alternate_form` non-null with `separate_contexts`, or with a non-PASS
   status → rejected.
5. Text 2, mocked L4 PASS: target `purr-suing`, `sound_substitution`, alternate
   `pursuing`, quotes `"stop dating the cad"` and `"the cat"`. With mocked L5
   and L6 PASS → `VALID_SOUNDALIKE_JOKE`, scope `SOUNDALIKE`,
   `detection_status == PUN`, and `per_age` populated.
6. Text 3, mocked L4 PASS `resegmentation` on `cat-nap` with parts
   `["cat", "nap"]` → accepted → `VALID_COMPOUND_SPLIT_JOKE`.
7. `detection_status_for(VALID_SOUNDALIKE_JOKE) == PUN`; `OUT_OF_SCOPE_HOMOPHONE`
   still maps to `OUT_OF_SCOPE`.
8. Version constants are `"7"` and `"5"`. A resume file holding records with
   `"6"` / `"4"` reuses none of them.
9. Budget: L4, L5 and L6 each make ≤ 1 request in a full mocked positive run;
   phonetic code makes none.
10. Homograph regression: the existing offline suite passes. With soundalike
    entries present, the homograph top 8 for every existing L3 fixture is
    unchanged (separate budget).
11. The `--resume` source fingerprint covers `src/crack/phonetics/`: changing
    any file there changes `_run_fingerprint`, so resume reuses no records.
    Today it hashes only top-level `*.py` files (`runner.py:345`,
    `package_root.glob("*.py")`, non-recursive), so phonetics changes would not
    invalidate resume.

## Depends on

[01](01_phonetic_core.md) and [02](02_soundalike_finder.md).

## Open decisions

- Closed set vs free proposal with local verification (team table: free + verify).
- Whether drum/drama counts, as `sound_pair` (team table: yes, reported separately).
- Separate soundalike budget (team table: separate 4 × 3).
- Order of the `SOUNDALIKE` row in `assign_scope_label` (diagnostic only;
  a single L4 choice means only one mechanism can PASS).
- "Phonological" age barrier. Adopting it changes `AgeEstimate.barrier` and needs
  an `AGE_RESPONSE_CONTRACT_VERSION` bump (`"3"` in `age_evidence.py`). design.md
  does not mention this.
- `EXCLUDED_MECHANISMS` content after the change.

## Risks

- Any prompt or source change already invalidates `--resume` through the
  fingerprint. A subpackage (`phonetics/`) is **not** hashed, because the glob is
  non-recursive (see [01](01_phonetic_core.md)).
- Re-validation at L0-post (`decisions.py:44`) re-scores alternates locally, so
  phonetics must be deterministic and available whenever L0-post runs. A resumed
  record must also re-validate.
- Mechanism confusion: "broke up" in text 1 may win as a homograph MWE, giving
  `VALID_HOMOGRAPH_JOKE` for the wrong reason.
- The LLM accepts forced sound links (catnap/kidnap). Validation must not
  accept an alternate on the model's word.
- The prompt change affects homograph behaviour. The README's October 4
  numbers need a live rerun (cost; NOT run).
- The web UI hard-codes labels in `index.html`; if one site is missed, a
  soundalike PUN renders as a non-PUN.
