# 01 — Phonetic core (P0 lexicon, P1 similarity, calibration)
Last updated: 2026-10-20 by soundalike handoff-verification session (offline, no code written)

Status: **not started**. Back to [HANDOFF](../HANDOFF.md).

## Checks this session

| Check | Command | Result |
|---|---|---|
| Phonetic deps in project Python | `py -3.11 -m pip install cmudict panphon==0.22.2` (2026-10-20, environment only; `pyproject.toml` unchanged) | **Installed**: cmudict 1.1.3, panphon 0.22.2. **Still missing**: g2p_en |
| Reference script output | `$env:PYTHONUTF8='1'; py -3.11 docs/soundalike/reference_wlev_fixed.py` (cmudict 1.1.3, panphon 0.22.2). Without `PYTHONUTF8=1`: `UnicodeDecodeError: 'charmap' codec`, because panphon `featuretable.py:83` opens its CSV with no encoding | **Ran** (2026-10-20); see next row |
| Six-pair values | same command | **Match design.md at 3 decimals.** `sim_maxlen` (`wlev_d`): knight/night 1.0000 (0.0000), cat/cad 0.9943 (0.0172), bat/pat 0.9943 (0.0172), pat/pit 0.9655 (0.1034), cat/cash 0.9540 (0.1379), drum/drama 0.8897 (0.5517) |
| δ table | same command | **Match** design.md to 4 decimals: t/d 0.0172, b/p 0.0172, ʌ/ɑ 0.0517, æ/ɪ 0.1034, t/ʃ 0.1379, m/ə 0.4828 |
| Lexicon source: `nltk.corpus.cmudict` pronunciations | `py -3.11 -c "import nltk; nltk.download('cmudict', quiet=True); from nltk.corpus import cmudict; d=cmudict.dict(); print([(w, d[w][0]) for w in [...]])"` (nltk 3.10.3; data is cmudict 0.7a) | **Match** design.md for all nine: cat K AE1 T, cad K AE1 D, cash K AE1 SH, drum D R AH1 M, drama D R AA1 M AH0, knight = night N AY1 T, bat B AE1 T, pat P AE1 T, pit P IH1 T. Also purr P ER1, pursuing P ER0 S UW1 IH0 NG (as [02](02_soundalike_finder.md) test 3 assumes) |
| Six pairs with `nltk.corpus.cmudict` | scratch copy of `reference_wlev_fixed.py` (outside the repo) with `import cmudict` / `cmudict.dict()` replaced by `nltk.corpus.cmudict.dict()`, run with `PYTHONUTF8=1` | **Match** at 3 decimals: identical output to the committed script (same six `sim_maxlen` and six δ values). The committed script is unchanged and remains the record of how the design numbers were produced |
| Licences | `pip show` metadata; `LICENSE`; `nltk_data/corpora/cmudict/README` | PyPI `cmudict` 1.1.3: **GPL-3.0-or-later**. CRACK: MIT. nltk 3.10.3: Apache-2.0. panphon 0.22.2: MIT. NLTK's cmudict data: CMU BSD-style licence (README lines 45–75) |
| μ_L percentiles, seed-pair sims | none | **NOT run**; numbers below are copied from design.md (scratch environment outside this repo) |
| Hand arithmetic on the design's six-pair values | sim = 1 − d/max(n,m) from the design's δ values | Consistent: e.g. pat/pit 1 − 0.1034/3 = 0.966; drum/drama 1 − (0.0517 + 0.5)/5 = 0.890; indel 1.0 → 0.790 |

## Goal

Produce the instructor's sound-similarity component (b): a deterministic, local,
graded phone-distance and word-similarity function with documented formulas, a
six-pair results table, and the name-aligned PanPhon weight fix. Nothing else in
the pipeline needs to be wired up for this to be submittable.

## Files to create/modify

- Create `src/crack/phonetics/__init__.py`
- Create `src/crack/phonetics/lexicon.py` (P0)
- Create `src/crack/phonetics/similarity.py` (P1)
- Create `src/crack/phonetics/calibration.py`
- Create the calibration table. design.md proposes `data/phonetic_calibration.json`,
  but `.gitignore` ignores `data/*` except `aoa_kuperman.csv`. Either add a
  `!data/phonetic_calibration.json` exception or keep the table next to the code
  (open decision).
- Create `scripts/fit_phonetic_calibration.py`, a seeded random-pair sampler that
  regenerates the calibration table.
- Create `tests/test_phonetics.py`
- Modify `pyproject.toml`: add only `panphon` (pin `==0.22.2`, the version
  whose weight bug is documented) and, if adopted, `g2p_en` (only after its
  licence is checked). New main dependency or new extra: open decision.
- Lexicon source: `nltk.corpus.cmudict` (NLTK data id `"cmudict"`), not the PyPI
  `cmudict` package. **Licence:** PyPI `cmudict` is GPL-3.0-or-later and CRACK
  is MIT; `nltk` is already a dependency and CMU's dictionary data is
  BSD-style. The data is not inside the nltk wheel: download it to
  `data/nltk_data` on first use, as `l2_senses.py` does for WordNet
  (`nltk.download(..., download_dir=str(NLTK_DIR), raise_on_error=True)`).
- Modify `src/crack/runner.py` `_run_fingerprint` if the modules live in a
  subpackage: it hashes only `package_root.glob("*.py")` (non-recursive), so
  `phonetics/*.py` changes would not invalidate `--resume`. Coordinate with
  [03](03_contract_l3_l4_l0post.md).

## Interfaces

From design.md, adjusted to the code:

```python
# src/crack/phonetics/lexicon.py
def pronunciations(word: str) -> list[tuple[str, ...]]           # nltk.corpus.cmudict ARPAbet, stress stripped; AH0 kept distinct
def span_phones(tokens: list[str]) -> list[tuple[str, ...]]      # concatenation over a 1-3 token span
def to_feature_vectors(arpabet: tuple[str, ...]) -> list[list[int]]
def lookup_source(word: str) -> Literal["cmudict", "g2p_en", "missing"]

# src/crack/phonetics/similarity.py
FEATURE_WEIGHTS: dict[str, float]        # loaded BY NAME from panphon data/feature_weights.csv
def phone_distance(a: list[int], b: list[int]) -> float               # δ in [0, 1]
def weighted_levenshtein(p, q, indel: float = 0.5) -> tuple[float, list[tuple[int | None, int | None]]]
@dataclass(frozen=True)
class SoundScore: sim: float; sim_cal: float; distance: float; pron_pair: tuple; alignment: list
def sound_similarity(x: str | list[str], y: str | list[str]) -> SoundScore   # max over pronunciation pairs

# src/crack/phonetics/calibration.py
def calibrate(sim: float, length: int) -> float   # (sim - mu_L) / (1 - mu_L)
```

Formulas (design.md § Formulas):

```
δ(a,b) = Σ_f w_f·|a_f − b_f| / (2·Σ_f w_f),  Σ_f w_f = 7.25
D[i][0] = 0.5·i;  D[0][j] = 0.5·j
D[i][j] = min(D[i−1][j] + 0.5, D[i][j−1] + 0.5, D[i−1][j−1] + δ(a_i, b_j))
sim = 1 − D[n][m] / max(n, m)
sim_cal = (sim − μ_L) / (1 − μ_L),  L = phone length of the longer word
```

`indel` comes from `Settings.PHONETIC_INDEL` when 03 adds it; until then it
stays a function default. No module here may import `providers.py`.

## Acceptance tests

`tests/test_phonetics.py`, offline. **First run `reference_wlev_fixed.py` in
this repo and pin the tests to the values it actually prints.** The design.md
values below are the expected values; record any difference in this file
before changing a test.

1. Name-aligned weights: `FEATURE_WEIGHTS["tense"] == 0.25`, `["long"] == 0.125`,
   `["velaric"] == 0.25`, `["hitone"] == ["hireg"] == 0`, sum `== 7.25`.
2. Library bug reproduced (regression guard): zipping
   `panphon.distance.Distance().fm.weights` against `FeatureTable().names` by
   position gives `tense` 0.125. The library weighted æ/ɪ cost is 1.25; the
   aligned cost is 1.5.
3. δ to 4 decimals: t/d 0.0172, b/p 0.0172, ʌ/ɑ 0.0517, æ/ɪ 0.1034,
   t/ʃ 0.1379, m/ə 0.4828.
4. Six pairs, `sim` to 3 decimals: knight/night 1.000, cat/cad 0.994,
   bat/pat 0.994, pat/pit 0.966, cat/cash 0.954, drum/drama 0.890. Also assert
   the ordering knight/night > cat/cad = bat/pat > pat/pit > cat/cash > drum/drama.
5. `indel=1.0` changes drum/drama to 0.790 and leaves the other five unchanged.
6. `nltk.corpus.cmudict` first entries: cat K AE1 T, cad K AE1 D, cash K AE1 SH,
   drum D R AH1 M, drama D R AA1 M AH0, knight = night N AY1 T, bat B AE1 T,
   pat P AE1 T, pit P IH1 T.
7. Max over pronunciations: wok/walk returns the best pair (design reports
   0.960 for wɑk/wɔk and 1.000 for wɑk/wɑk; pin to the observed value).
8. `calibrate(μ_L, L) == 0` and `calibrate(1.0, L) == 1` for every stored L.
   Do **not** assert design.md's μ₃ = 0.735, μ₄ = 0.719, μ₅ = 0.730 as truth:
   they come from one seeded sample outside this repo.
9. Determinism: two calls return identical `SoundScore`s, and no network or
   provider access happens (monkeypatch `crack.providers` to raise).
10. Windows encoding: the six-pair test (4) passes under plain
    `py -3.11 -m pytest` on Windows, with `PYTHONUTF8` unset. See Risks.
11. Licence: no new GPL dependency. `pyproject.toml` gains only `panphon`
    (and `g2p_en` only after its licence is checked); the PyPI `cmudict`
    package is not added, and no module under `src/crack/phonetics/` imports
    it (the lexicon uses `nltk.corpus.cmudict`).

## Depends on

Nothing. This can start immediately.

## Open decisions

- Primary metric (team table): custom weighted Levenshtein, with ALINE and the
  bounded score as comparison columns.
- How to vectorise diphthongs and affricates per ARPAbet phone (see Risks).
- Whether `g2p_en` is adopted, and the behaviour on a CMUdict miss when it is
  not (raise, or mark `lookup_source="missing"` so L0-post can use
  `OUT_OF_SCOPE_HOMOPHONE`).
- Where the calibration table lives (gitignored `data/` vs package data).
- Dependencies as main requirements or as an optional extra.

## Risks

- **Segmentation drift between reference and interface.** `reference_wlev_fixed.py`
  builds an IPA string and segments it with PanPhon
  (`ft.word_to_vector_list(ipa)`). design.md's `to_feature_vectors` builds one
  vector per ARPAbet phone, and design.md itself notes that PanPhon splits
  diphthongs and untied affricates (aɪ → a + ɪ, tʃ → t + ʃ). The two can
  therefore differ in both δ and n/m (and so in sim) for AY, AW, OY, EY, OW, CH
  and JH. The six required pairs avoid this: the only diphthong is in
  knight/night, which is identical. Seed pairs such as propane/profane (eɪ) and
  alleged/a ledge (dʒ) may drift. Pin tests to values the reference script
  actually produces, and record every drift here. μ_L must be fitted with the
  same segmentation used for scoring, because L changes too.
- design.md's six-pair `sim` values and six δ values were reproduced in this
  repo on 2026-10-20 (cmudict 1.1.3, panphon 0.22.2). μ_L percentiles and
  seed-pair sims are still unreproduced.
- **panphon 0.22.2 is not Windows-safe.** It opens its CSVs without an encoding
  (`featuretable.py:83`), so on Windows (cp1252) `panphon.FeatureTable()` fails
  with `UnicodeDecodeError: 'charmap' codec` unless `PYTHONUTF8=1`. The
  phonetics module must work on Windows without that env var, e.g. by setting
  the flag in a documented test command or by a guarded workaround
  (acceptance test 10).
- PanPhon upstream may fix the weight bug, which would change the "library"
  comparison column. Pin the version.
- `ARPA2IPA` maps every ER to ɝ, including unstressed ER0, which is often ɚ.
  Whether PanPhon's table has ɝ is unverified.
- CMUdict is American English only (dialect decision).
- **Dictionary revision.** NLTK's data is cmudict 0.7a (123,455 words); the
  PyPI package ships a different revision (126,052 words). The nine words
  checked are identical, but other entries may differ, so pin tests to
  `nltk.corpus.cmudict` output. PyPI cmudict 1.1.3 was installed only to run
  the reference script on 2026-10-20, then uninstalled (GPL-3.0). Rerunning
  reference_wlev_fixed.py as committed requires reinstalling it temporarily;
  implementation code must use nltk.corpus.cmudict.
- **cmudict data download.** Offline tests block `socket.connect`
  (`tests/conftest.py`), so a test run on a machine without
  `data/nltk_data/corpora/cmudict` cannot download it during the run.
- `g2p_en`'s dependency footprint and data downloads are unverified.
- Compressed scale: raw sims for random pairs cluster near 0.72–0.74 (design
  claim), so any threshold on raw sim is fragile.
