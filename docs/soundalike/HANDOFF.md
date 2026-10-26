# HANDOFF — CRACK soundalike extension (Project 2)
Last updated: 2026-10-21 by soundalike docs-sync session (workstreams 01–03 merged; offline, no API calls)

---

## October 25 resource update

The current implementation supersedes the original NLTK-CMUdict choice below:
P0 uses official cmusphinx/cmudict commit `74790861f652b15e4ac49015a90074ad62a27690`,
L2 uses Open English Wordnet 2025, and historical SemCor counts still come from
Princeton WordNet 3.0 via exact sense keys. Calibration has been regenerated.
The October 23 live results describe the previous resources. New local checks
and exact provenance are in [the refresh report](../resource_refresh_20261025.md).

## Goal

Project 2 extends CRACK from homographic wordplay (one spelling, two meanings)
and compound resegmentation to soundalike (heterographic) wordplay, where a word
in the text sounds like a different word or phrase and the difference in
pronunciation fits different parts of the text. The extension adds a
deterministic local phonetic module to find and score soundalikes. CRACK's
existing L4 anchoring, L5 resolution and L6 distinctness checks then decide
whether a soundalike creates incongruity. The LLM never decides what sounds
alike, and no extra model requests are added. Design and evidence:
[design.md](design.md) (the original design record; not updated); implemented
architecture: [ARCHITECTURE.md § Soundalike wordplay extension](../../ARCHITECTURE.md#soundalike-wordplay-extension).

## Instructor deliverables

| Deliverable | Produced by | Status |
|---|---|---|
| Sound-similarity method with formulas, and why it is adequate (component b) | [01](handoff/01_phonetic_core.md) | **Done** (PR #5). Formulas in `src/crack/phonetics/similarity.py` and `calibration.py` docstrings and in ARCHITECTURE.md |
| Similarity results for {cat,cad} {cat,cash} {drum,drama} {knight,night} {bat,pat} {pat,pit} | [01](handoff/01_phonetic_core.md) | **Done.** sim: knight/night 1.000, cat/cad 0.994, bat/pat 0.994, pat/pit 0.966, cat/cash 0.954, drum/drama 0.890; pinned by `tests/test_phonetics.py`; reproduced on Windows |
| Finding utterances that sound similar (component a) | [02](handoff/02_soundalike_finder.md); [05](handoff/05_lexicon_neighbours.md) optional | **Done** for in-text pairs and hyphen merges (PR #6). Lexicon neighbours (05) not started |
| Results on the three test texts (drum/drama, purr-suing, cat-nap) | [03](handoff/03_contract_l3_l4_l0post.md) + [04](handoff/04_eval_data.md) | **Live** (gpt-6-luna, 2026-10-23, after fixes): all three correct with the right mechanism (purr-suing and drum/drama → `VALID_SOUNDALIKE_JOKE`, cat-nap → `VALID_COMPOUND_SPLIT_JOKE`). The first live run got 1/3 (two misquoted answers); runs vary |
| ≥ 20 soundalike jokes | [04](handoff/04_eval_data.md) | **Built**: 25 seed positives in `corpus/soundalike_*.jsonl` (+8 known, +3 test texts). **Blind double labelling NOT run** |
| ≥ 20 negatives | [04](handoff/04_eval_data.md) | **Built**: 29 seed minimal-pair negatives typed A–E (+11 known, +3 test). **Blind double labelling NOT run** |

The three test texts are a separate slice and do not count towards the 20.

## Current status

Workstreams **01, 02 and 03 are merged** into `main` (PRs #5, #6, #7), together
with the Windows offline-guard fix (PR #4). CRACK can now output
`VALID_SOUNDALIKE_JOKE`; see the
[architecture section](../../ARCHITECTURE.md#soundalike-wordplay-extension).
Workstream 04 is also merged (PR #9). Optional workstreams 05–06 remain unimplemented.

**Live results (2026-10-23, gpt-6-luna).** Soundalike corpus after the live-run
fixes: binary 73/79 (92.4%), all three test texts correct. Homograph regression:
binary 54/60 in two runs (October 4: 56/60); J22 is the one repeat loss. The
team chose to report this as is. See README and `docs/evaluations/`. Offline, the
homograph top-8 shortlist is unchanged for all 74 corpus and fixture texts, and
the L5/L6 prompts are byte-identical for non-soundalike readings.

`panphon==0.22.2` is a main dependency. `g2p_en` is not adopted, and no
word-frequency package is installed (05 would need one).

**Lexicon source (decided 2026-10-20):** `nltk.corpus.cmudict`, not the PyPI
`cmudict` package. Licence: PyPI `cmudict` is GPL-3.0-or-later and CRACK is MIT;
`nltk` is already a dependency and CMU's dictionary data is BSD-style.
PyPI cmudict 1.1.3 was installed only to run the reference script on
2026-10-20, then uninstalled (GPL-3.0). Rerunning reference_wlev_fixed.py as
committed requires reinstalling it temporarily; implementation code must use
nltk.corpus.cmudict.

**About design.md's final "Verification note".** It refers to a scratch
environment outside this repository (`/home/claude/research_notes/...`,
`/home/claude/jyz922/crack`) that is not available here. The only reproducible
artifact in this repo is [reference_wlev_fixed.py](reference_wlev_fixed.py).
On 2026-10-20 that script reproduced the six-pair `sim` values and the six δ
values in this repo (see [01](handoff/01_phonetic_core.md)). Every other
phonetic number in design.md (μ_L percentiles, seed-pair sims, index sizes)
remains unverified until someone runs it here. Do not edit design.md; record
any differences in the workstream file.

## Planning-session checks (2026-10-19/20, historical)

These record the code **before** workstreams 01–03. Rows marked superseded no
longer describe `main`; each workstream file has its own current checks.


| Check | Command | Result |
|---|---|---|
| L1 regex splits hyphenated forms | `_TOKEN.findall(...)` on both texts (py) | **Confirmed**: `purr`,`suing`; `cat`,`nap`. Still true for `tokens`; hyphen spans are now kept in `hyphen_groups` (02) |
| L4 prompt forbids differently spelled soundalikes in splits | read `src/crack/prompts/l4_anchoring.md` | **Confirmed**, lines 33–34. Kept for splits; soundalikes now have their own prompt section (03) |
| `OUT_OF_SCOPE_HOMOPHONE` exists but nothing produces it | read `enums.py`, `runner._l0_post_layer`, `l0_scope.assign_scope_label` | **Confirmed**: `is_homophone` is set only from a previous `record.final`. Superseded in part: soundalike PASS now gives `SOUNDALIKE` (03) |
| Contract versions | read `validation.py:11`, `decisions.py:12` | **Confirmed** then: "6" / "4". **Superseded**: now "7" / "5" (03) |
| `CandidateEntry`, `L4Result` use `extra="forbid"` | read `schema.py` | **Confirmed** (also `_L4LLMResponse` in `l4_anchoring.py`) |
| L3 score | read `l3_candidates.py:32-33,58` | **Confirmed**: `0.7*contrast + 0.3*balance` |
| No heterographic corpus items | id prefixes, `heterograph\|homophone` grep over `corpus/*.jsonl` | **Confirmed**: IDs are `J/D/N` and `hom_` only; 0 matches |
| `scripts/prepare_semeval.py` builds only the homographic split | grep | **Confirmed** |
| WordNet lists `catnap`; `compound_splits("catnap")` | `py -3.11 -c ...` | `nap.n.04`, `nap.v.01`; `[('cat','nap')]` |
| L4 accepts a resegmentation of `cat-nap` | `validate_l4_response` with term `catnap` and `cat-nap` | **Rejected both** then. **Superseded**: term `cat-nap` with parts `cat`+`nap` is accepted (03) |
| Phonetic deps installed | `py -3.11 -m pip install cmudict panphon==0.22.2` (2026-10-20, environment only) | **Installed** then: cmudict 1.1.3, panphon 0.22.2. **Superseded**: PyPI cmudict uninstalled (GPL); panphon is now a dependency |
| Offline suite | `py -3.11 -m pytest -m "not live" -q -p no:cacheprovider` | see "Offline suite" below |
| Reference script | `$env:PYTHONUTF8='1'; py -3.11 docs/soundalike/reference_wlev_fixed.py` (after `py -3.11 -m pip install cmudict panphon==0.22.2`). Without `PYTHONUTF8=1` it crashes with `UnicodeDecodeError: 'charmap' codec` because panphon 0.22.2 `featuretable.py:83` opens its CSV with no encoding (cp1252 on Windows) | **Ran** (2026-10-20); output under "Six-pair values" |
| Six-pair values | same command | **Match design.md at 3 decimals.** `sim_maxlen`: knight/night 1.0000, cat/cad 0.9943, bat/pat 0.9943, pat/pit 0.9655, cat/cash 0.9540, drum/drama 0.8897 |
| Pronunciations from `nltk.corpus.cmudict` | `nltk.download('cmudict')`, then `cmudict.dict()[w][0]` for the nine design words plus purr, pursuing (nltk 3.10.3, cmudict 0.7a) | **Match** design.md for all nine; details in [01](handoff/01_phonetic_core.md) |
| Six pairs with `nltk.corpus.cmudict` | scratch copy of the reference script (outside the repo) with the lexicon swapped to `nltk.corpus.cmudict.dict()`, `PYTHONUTF8=1` | **Match** at 3 decimals (identical output). The committed script is unchanged |
| Licences | `pip show`, `LICENSE`, `nltk_data/corpora/cmudict/README` | PyPI `cmudict` GPL-3.0-or-later; CRACK MIT; nltk Apache-2.0; panphon MIT; CMU data BSD-style |
| Calibration percentiles, seed-pair sims | none | **NOT run** then. **Superseded**: `data/phonetic_calibration.json` fitted in this repo (01); seed-pair sims still unverified |
| Live suite / any provider call | none | **NOT run this session** |

## Design vs code (planning-time gaps, all resolved)

All eight gaps found while planning are now closed:

| Gap | Resolved by |
|---|---|
| 1. Hyphen resegmentation | 02 (L2 whole-word + split senses under `cat-nap`) and 03 (validation joins parts without hyphens) |
| 2. Exact-key contracts | 03 (`alternate_form` in `L4Result`, `L4_RESPONSE_FIELDS`, `_L4LLMResponse`) |
| 3. Hard-coded label sets | 03 (runner, `serve.py`, all three `index.html` sites; guarded by a test) |
| 4. Age contract | Deferred by team decision; age contract unchanged, alternates only added to the AoA table |
| 5. `EXCLUDED_MECHANISMS` | 03 (`heterographic_homophone` moved to accepted) |
| 6. Calibration file location | 01 (`.gitignore` exception for `data/phonetic_calibration.json`) |
| 7. Interpreter | Documented: use `py -3.11` |
| 8. `--resume` misses subpackages | 01 (`rglob`), tested |

Original notes:

1. **Hyphen resegmentation does not "just work."** design.md says that passing
   "catnap" through `compound_splits` lets the existing resegmentation path
   handle test text 3. It doesn't. `validate_l4_response` requires both quotes
   to equal the term and `"".join(split_parts)` to equal the term. With term
   `catnap`, the quote is not a verbatim substring of "cat-nap". With term
   `cat-nap`, the joined parts `catnap` do not match. L2 `retrieve` also only
   adds whole-word senses for tokens, so `_split` would return `None` without
   senses for `catnap`. Owned by [02](handoff/02_soundalike_finder.md) and
   [03](handoff/03_contract_l3_l4_l0post.md).
2. **More exact-key contracts than design.md names.** Besides `L4Result`, the L4
   response key set `L4_RESPONSE_FIELDS` (`validation.py`) and the Gemini
   `response_schema` `_L4LLMResponse` (`l4_anchoring.py`) are exact-key. All
   three need `alternate_form`.
3. **More hard-coded label sets.** Besides the "decided" set in
   `_l0_post_layer`, the new label must be added to the per-age block
   (`runner.py:290`), `format_analysis_report` (`runner.py:533,546`),
   `serve.py:217` and `static/index.html` (lines 1296, 1703, 1726).
4. **Age contract.** design.md's "phonological" L6 age barrier would change
   `AgeEstimate.barrier` (a `Literal`), which is an age-contract change
   (`AGE_RESPONSE_CONTRACT_VERSION = "3"` in `age_evidence.py`). The design does
   not mention this. The L7 AoA payload is built in `age_evidence.age_inputs`.
5. **Settings.** `config.py` `EXCLUDED_MECHANISMS` contains
   `heterographic_homophone`. It is only read by scripts as provenance, but it
   now contradicts the plan.
6. **Calibration file location.** `.gitignore` has `data/*` with only
   `aoa_kuperman.csv` excepted, so the planned `data/phonetic_calibration.json`
   would not be committed.
7. **Interpreter.** Plain `python` on this machine is 3.10 and cannot import
   `crack` (`StrEnum`; `requires-python >= 3.11`). Use `py -3.11`, which has the
   editable install.
8. **`--resume` misses subpackages.** `_run_fingerprint` (`runner.py:345`)
   hashes only `package_root.glob("*.py")` (non-recursive) plus prompts, so
   changes under `src/crack/phonetics/` would not invalidate resume. Owned by
   [03](handoff/03_contract_l3_l4_l0post.md), acceptance test 11.

## Build order

1. [01 Phonetic core](handoff/01_phonetic_core.md): lexicon, similarity,
   calibration. Produces the required formulas and six-pair numbers, and
   nothing else depends on it being wired in.
2. [02 Soundalike finder](handoff/02_soundalike_finder.md): in-text pairs plus
   hyphen merge/split, `L1Result.hyphen_groups`, and L2 hyphen-joined
   `compound_splits`.
3. [03 Contract, L3, L4, L0-post](handoff/03_contract_l3_l4_l0post.md):
   schemas, L3 soundalike entries, the L4 prompt section and validation, enums,
   L0-post, and both version bumps together.
4. [04 Evaluation data](handoff/04_eval_data.md): the minimal-pair file,
   heterographic SemEval preparation, the eval script and baselines.
5. [05 Lexicon neighbours](handoff/05_lexicon_neighbours.md): k ≤ 2 phone
   deletion index plus a frequency floor. Only unseen-target cases need it.
6. [06 Optional extensions](handoff/06_optional_extensions.md): only if the
   evaluation shows L4 picking wrong alternates.

## Team decisions

| Decision | Chosen | Where |
|---|---|---|
| May L4 propose an alternate not in the supplied list? | **Yes, verified locally** at the p95 random-pair similarity (`PHONETIC_VERIFY_PERCENTILE`; p99 until the first live run); finder-supplied alternates are accepted as is; a failed check is a NON_PUN finding | 03 |
| Does an in-text juxtaposition (drum/drama) count? | **Yes, as `sound_pair`**, reported separately from `sound_substitution` | 03 |
| Primary metric | **Custom weighted Levenshtein** over name-aligned PanPhon features (ALINE and the library score as comparison columns) | 01 |
| Thresholds | **Finder: p95** of random same-length pairs (raw 0.75 flagged 554 corpus pairs). **Verification: p95** (was p99; lowered 2026-10-23 after the live run) | 02, 03 |
| Separate shortlist budget for soundalikes | **Separate** (`L3_SOUNDALIKE_TOP_K = 4`) | 03 |
| Phonological age barrier | **Deferred** | 03 |
| Local language model diagnostic | Deferred (06) | — |
| Dialect | Documented limit: CMUdict American English only | 01 |

## Workstreams

| # | File | Scope | Depends on | Status |
|---|---|---|---|---|
| 01 | [handoff/01_phonetic_core.md](handoff/01_phonetic_core.md) | P0 lexicon, P1 similarity, calibration | — | **merged** (PR #5) |
| 02 | [handoff/02_soundalike_finder.md](handoff/02_soundalike_finder.md) | P2 in-text pairs, hyphen merge/split, L1 `hyphen_groups`, L2 hyphen splits | 01 | **merged** (PR #6) |
| 03 | [handoff/03_contract_l3_l4_l0post.md](handoff/03_contract_l3_l4_l0post.md) | Schemas, L3 entries, L4 prompt + validation, enums, L0-post, version bumps | 01, 02 | **merged** (PR #7); live corpus rerun pending |
| 04 | [handoff/04_eval_data.md](handoff/04_eval_data.md) | Minimal-pair data, heterographic SemEval, eval script, baselines | 01 (data file can start now) | merged (PR #9); live runs done; labelling pending |
| 05 | [handoff/05_lexicon_neighbours.md](handoff/05_lexicon_neighbours.md) | k ≤ 2 phone deletion index, frequency floor | 01, 02 | not started |
| 06 | [handoff/06_optional_extensions.md](handoff/06_optional_extensions.md) | LM re-ranking, DP resegmentation, curated list, dual-support diagnostic | 03, 04 results | not started |

## Offline suite

Current: Linux after 03, 541 passed. Windows was last confirmed after 01
(488 passed, 2 skipped; the skips are panphon-loader comparisons that skip by
design on Windows); a Windows run after 02/03 is not recorded here. The rows below are the
planning-time history.


| Check | Command | Result |
|---|---|---|
| Full offline suite | `py -3.11 -m pytest -m "not live" -q -p no:cacheprovider` | **Collection error**: `tests/test_web_contract.py` → `ModuleNotFoundError: No module named 'fastapi'` |
| After test extra | `py -3.11 -m pip install -e ".[test]"`, then the same command | **Same error**. `[test]` is only pytest + pytest-cov; fastapi is in `[web]` |
| Suite without the web file | same, `--ignore=tests/test_web_contract.py` | **398 passed, 4 failed, 10 deselected**. All 4 failures are `ModuleNotFoundError: fastapi` (`test_reliability.py::test_web_assesses_only_selected_age[False/True]`, `test_system_design.py::test_age_failure_preserves_detection_without_default_age_pass`, `::test_frontend_hides_unconfirmed_readings`) |
| Suite with `[web]` installed | `py -3.11 -m pip install -e ".[test,web]"`, then `py -3.11 -m pytest -m "not live" -q -p no:cacheprovider` | **Ran** (2026-10-20): **403 passed, 45 failed, 10 deselected**. All 45 raise the `conftest.py` guard's `AssertionError: Offline tests must mock provider calls; network access is disabled` on a `127.0.0.1` connect inside Starlette's `TestClient`: 43 in `tests/test_web_contract.py` plus `test_reliability.py::test_web_assesses_only_selected_age[False/True]`. Likely cause: on Windows, asyncio's `socket.socketpair()` is emulated with a localhost TCP connect, which the guard blocks |

No test reads ARCHITECTURE.md or `docs/soundalike/`, so these failures are
environmental and not caused by this docs change.

### Known environment issue (resolved by PR #4)

On Windows, 45 web tests fail because the `tests/conftest.py` offline guard
patches `socket.socket.connect`, and asyncio's Windows `socketpair()` fallback
connects to `127.0.0.1`. The failure is already present on `main` (this branch
changes only docs) and is unrelated to this work. The proposed fix, allowing
loopback addresses in the guard, is a separate `tests/` change and not part of
this commit.
