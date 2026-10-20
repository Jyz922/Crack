# HANDOFF — CRACK soundalike extension (Project 2)
Last updated: 2026-10-20 by soundalike handoff-verification session (offline, no API calls, no source changes)

---

## Goal

Project 2 extends CRACK from homographic wordplay (one spelling, two meanings)
and compound resegmentation to soundalike (heterographic) wordplay, where a word
in the text sounds like a different word or phrase and the difference in
pronunciation fits different parts of the text. The extension adds a
deterministic local phonetic module to find and score soundalikes. CRACK's
existing L4 anchoring, L5 resolution and L6 distinctness checks then decide
whether a soundalike creates incongruity. The LLM never decides what sounds
alike, and no extra model requests are added. Design and evidence:
[design.md](design.md); planned architecture:
[ARCHITECTURE.md § Planned: soundalike wordplay extension](../../ARCHITECTURE.md#planned-soundalike-wordplay-extension-not-yet-implemented).

## Instructor deliverables

| Deliverable | Produced by | Status |
|---|---|---|
| Sound-similarity method with formulas, and why it is adequate (component b) | [01](handoff/01_phonetic_core.md) | Formulas drafted in design.md; no code |
| Similarity results for {cat,cad} {cat,cash} {drum,drama} {knight,night} {bat,pat} {pat,pit} | [01](handoff/01_phonetic_core.md) | **Reproduced in this repo on 2026-10-20** with `reference_wlev_fixed.py` (all six match design.md at 3 decimals); no `src/` implementation yet |
| Soundalike finder (component a) | [02](handoff/02_soundalike_finder.md), [05](handoff/05_lexicon_neighbours.md) | Not started |
| Results on the three test texts (drum/drama, purr-suing, cat-nap) | [03](handoff/03_contract_l3_l4_l0post.md) + [04](handoff/04_eval_data.md) | design.md has design-time **expectations only**, not results |
| ≥ 20 soundalike jokes | [04](handoff/04_eval_data.md) | 29 drafts in design.md; not yet a data file or labelled |
| ≥ 20 negatives | [04](handoff/04_eval_data.md) | 39 drafts in design.md; not yet a data file or labelled |

The three test texts are a separate slice and do not count towards the 20.

## Current status

Design done; no code. Nothing under `src/`, `tests/`, `corpus/`, `data/` or
`scripts/` has been changed for Project 2. As of 2026-10-20, `panphon` 0.22.2
is installed in the project Python 3.11 environment (environment only;
`pyproject.toml` is unchanged). `g2p_en` and a word-frequency
package are **not installed**.

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

## Checks this session

| Check | Command | Result |
|---|---|---|
| L1 regex splits hyphenated forms | `_TOKEN.findall(...)` on both texts (py) | **Confirmed**: `purr`,`suing`; `cat`,`nap` |
| L4 prompt forbids differently spelled soundalikes in splits | read `src/crack/prompts/l4_anchoring.md` | **Confirmed**, lines 33–34 |
| `OUT_OF_SCOPE_HOMOPHONE` exists but nothing produces it | read `enums.py`, `runner._l0_post_layer`, `l0_scope.assign_scope_label` | **Confirmed**: `is_homophone` is set only from a previous `record.final` |
| Contract versions | read `validation.py:11`, `decisions.py:12` | **Confirmed**: `RESPONSE_CONTRACT_VERSION = "6"`, `CANDIDATE_SEARCH_VERSION = "4"` |
| `CandidateEntry`, `L4Result` use `extra="forbid"` | read `schema.py` | **Confirmed** (also `_L4LLMResponse` in `l4_anchoring.py`) |
| L3 score | read `l3_candidates.py:32-33,58` | **Confirmed**: `0.7*contrast + 0.3*balance` |
| No heterographic corpus items | id prefixes, `heterograph\|homophone` grep over `corpus/*.jsonl` | **Confirmed**: IDs are `J/D/N` and `hom_` only; 0 matches |
| `scripts/prepare_semeval.py` builds only the homographic split | grep | **Confirmed** |
| WordNet lists `catnap`; `compound_splits("catnap")` | `py -3.11 -c ...` | `nap.n.04`, `nap.v.01`; `[('cat','nap')]` |
| L4 accepts a resegmentation of `cat-nap` | `validate_l4_response` with term `catnap` and `cat-nap` | **Rejected both** (see "Design vs code" below) |
| Phonetic deps installed | `py -3.11 -m pip install cmudict panphon==0.22.2` (2026-10-20, environment only) | **Installed**: cmudict 1.1.3, panphon 0.22.2. **Still missing**: g2p_en, wordfreq |
| Offline suite | `py -3.11 -m pytest -m "not live" -q -p no:cacheprovider` | see "Offline suite" below |
| Reference script | `$env:PYTHONUTF8='1'; py -3.11 docs/soundalike/reference_wlev_fixed.py` (after `py -3.11 -m pip install cmudict panphon==0.22.2`). Without `PYTHONUTF8=1` it crashes with `UnicodeDecodeError: 'charmap' codec` because panphon 0.22.2 `featuretable.py:83` opens its CSV with no encoding (cp1252 on Windows) | **Ran** (2026-10-20); output under "Six-pair values" |
| Six-pair values | same command | **Match design.md at 3 decimals.** `sim_maxlen`: knight/night 1.0000, cat/cad 0.9943, bat/pat 0.9943, pat/pit 0.9655, cat/cash 0.9540, drum/drama 0.8897 |
| Pronunciations from `nltk.corpus.cmudict` | `nltk.download('cmudict')`, then `cmudict.dict()[w][0]` for the nine design words plus purr, pursuing (nltk 3.10.3, cmudict 0.7a) | **Match** design.md for all nine; details in [01](handoff/01_phonetic_core.md) |
| Six pairs with `nltk.corpus.cmudict` | scratch copy of the reference script (outside the repo) with the lexicon swapped to `nltk.corpus.cmudict.dict()`, `PYTHONUTF8=1` | **Match** at 3 decimals (identical output). The committed script is unchanged |
| Licences | `pip show`, `LICENSE`, `nltk_data/corpora/cmudict/README` | PyPI `cmudict` GPL-3.0-or-later; CRACK MIT; nltk Apache-2.0; panphon MIT; CMU data BSD-style |
| Calibration percentiles, seed-pair sims | none | **NOT run**; taken from design.md only |
| Live suite / any provider call | none | **NOT run this session** |

## Design vs code (use the code's truth)

All seven claims listed above hold. These eight gaps were found in addition:

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

## Open team decisions (from design.md)

| Decision | Options | Recommendation |
|---|---|---|
| May L4 propose an alternate not in the supplied list? | Closed set only / free proposal verified locally | Free proposal with local verification at τ_verify. It keeps one request and recovers retrieval misses, which were 19% of failures in PunGraph |
| Does an in-text juxtaposition (drum/drama) count as soundalike wordplay? | Yes, as `sound_pair` / No, out of scope | Yes, but report it as a separate mechanism, because it does not test target recovery |
| Primary metric for the submission | Custom weighted Levenshtein / ALINE / bounded library score | Custom weighted Levenshtein as primary, with ALINE and the bounded score as comparison columns |
| Thresholds τ_retrieve, τ_verify | Fixed from the notes / fitted | Fit on a dev split of seed pairs plus random pairs. Start retrieval at raw ≥ 0.75 and verification at sim_cal around the random-pair 99th percentile, then tune |
| Separate shortlist budget for soundalikes | Share the top 8 / separate 4 × 3 | Separate, so homograph regressions stay comparable |
| Local language model for the diagnostic | None / distilgpt2 / masked-LM pseudo-likelihood ([Salazar et al. 2020](https://aclanthology.org/2020.acl-main.240)) | Defer. Add it only as a diagnostic after the core works |
| Dialect | CMUdict American only / add variants | Document the limit. CMUdict is American English, so pairs that depend on dialect mergers such as cot/caught are scored by CMUdict's listed pronunciations only |

## Workstreams

| # | File | Scope | Depends on | Status |
|---|---|---|---|---|
| 01 | [handoff/01_phonetic_core.md](handoff/01_phonetic_core.md) | P0 lexicon, P1 similarity, calibration | — | not started |
| 02 | [handoff/02_soundalike_finder.md](handoff/02_soundalike_finder.md) | P2 in-text pairs, hyphen merge/split, L1 `hyphen_groups`, L2 hyphen splits | 01 | not started |
| 03 | [handoff/03_contract_l3_l4_l0post.md](handoff/03_contract_l3_l4_l0post.md) | Schemas, L3 entries, L4 prompt + validation, enums, L0-post, version bumps | 01, 02 | not started |
| 04 | [handoff/04_eval_data.md](handoff/04_eval_data.md) | Minimal-pair data, heterographic SemEval, eval script, baselines | 01 (data file can start now) | not started |
| 05 | [handoff/05_lexicon_neighbours.md](handoff/05_lexicon_neighbours.md) | k ≤ 2 phone deletion index, frequency floor | 01, 02 | not started |
| 06 | [handoff/06_optional_extensions.md](handoff/06_optional_extensions.md) | LM re-ranking, DP resegmentation, curated list, dual-support diagnostic | 03, 04 results | not started |

## Offline suite

| Check | Command | Result |
|---|---|---|
| Full offline suite | `py -3.11 -m pytest -m "not live" -q -p no:cacheprovider` | **Collection error**: `tests/test_web_contract.py` → `ModuleNotFoundError: No module named 'fastapi'` |
| After test extra | `py -3.11 -m pip install -e ".[test]"`, then the same command | **Same error**. `[test]` is only pytest + pytest-cov; fastapi is in `[web]` |
| Suite without the web file | same, `--ignore=tests/test_web_contract.py` | **398 passed, 4 failed, 10 deselected**. All 4 failures are `ModuleNotFoundError: fastapi` (`test_reliability.py::test_web_assesses_only_selected_age[False/True]`, `test_system_design.py::test_age_failure_preserves_detection_without_default_age_pass`, `::test_frontend_hides_unconfirmed_readings`) |
| Suite with `[web]` installed | `py -3.11 -m pip install -e ".[test,web]"`, then `py -3.11 -m pytest -m "not live" -q -p no:cacheprovider` | **Ran** (2026-10-20): **403 passed, 45 failed, 10 deselected**. All 45 raise the `conftest.py` guard's `AssertionError: Offline tests must mock provider calls; network access is disabled` on a `127.0.0.1` connect inside Starlette's `TestClient`: 43 in `tests/test_web_contract.py` plus `test_reliability.py::test_web_assesses_only_selected_age[False/True]`. Likely cause: on Windows, asyncio's `socket.socketpair()` is emulated with a localhost TCP connect, which the guard blocks |

No test reads ARCHITECTURE.md or `docs/soundalike/`, so these failures are
environmental and not caused by this docs change.

### Known environment issue

On Windows, 45 web tests fail because the `tests/conftest.py` offline guard
patches `socket.socket.connect`, and asyncio's Windows `socketpair()` fallback
connects to `127.0.0.1`. The failure is already present on `main` (this branch
changes only docs) and is unrelated to this work. The proposed fix, allowing
loopback addresses in the guard, is a separate `tests/` change and not part of
this commit.
