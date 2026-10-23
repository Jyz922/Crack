# 04 — Evaluation data, heterographic SemEval, eval script, baselines
Last updated: 2026-10-21 by soundalike eval-data session (offline; no provider calls)

Status: **merged** (PR #9); live runs done 2026-10-23; **blind double labelling still pending**. Back to [HANDOFF](../HANDOFF.md).

## Results so far (2026-10-21)

| Check | Command | Result |
|---|---|---|
| Corpus built | `py -3.11 scripts/build_soundalike_corpus.py` | seed 25 positives / 29 negatives (incl. 4 spare positives S31–S34 + their negatives); known 8 / 11; test_text 3 / 3. Files load with `crack.corpus` |
| Blind double labelling | `scripts/soundalike_labelling.py sheets`, then `agree` | **NOT run** (needs two people). Sheets are in `docs/soundalike/labelling/` |
| Heterographic SemEval split | `py -3.11 scripts/prepare_semeval.py --heterographic` | 1,780 contexts, 1,271 puns, 509 non-puns; 1,098 gold targets. Homographic outputs regenerate byte-identically |
| Always-pun baseline (SemEval het) | `scripts/evaluate_soundalike.py baselines` | P 0.714, R 1.000, **F1 0.833** (acceptance 3 met) |
| "≥ 9 tokens OR Tom" (L1 tokenisation) | same | **F1 0.807** (design.md: 0.806); "Tom" in 224 puns, 0 non-puns |
| P1 graded vs binary | `scripts/evaluate_soundalike.py metric` | Six pairs: graded gives 5 distinct values, binary 3 (cat/cad = pat/pit = cat/cash = 0.667). Soundalike-vs-random ROC-AUC: graded 0.994, **binary 1.000** (imperfect pairs only, n = 12: graded 0.983, binary 1.000). Separating soundalikes from random words is easy for both; graded's contribution is ordering close pairs |
| P2 finder recall | `scripts/evaluate_soundalike.py finder` | Target supplied for **2/35** corpus positives (only test texts) and **2/1,098** SemEval puns (0.2%). The finder fires on 10/43 negatives |
| Verification of L4-proposed alternates (p99) | phonetics on each positive's pun/target | 3 seed positives fail p99 even if L4 names the right target: tents/tense 0.900, yeast/least 0.929, tuna/tune 0.875 (and drum/drama passes only because the finder supplies it) |
| Detection rescoring | `scripts/evaluate_soundalike.py detection runs/<run>/records.jsonl` | Implemented; see the live run below |
| **First live run** (gpt-6-luna, authored labels, before the 2026-10-23 fixes) | `crack.runner --input corpus/soundalike_blind.jsonl --backend openai` → `runs/20261023T172942Z` | All 79: P 0.862, R 0.694, F1 0.769, decided 68/79. 11 `EXECUTION_FAILED`: 5 from a content-free `"": ""` the model appended (S08, S25, S31, S34, T2), 5 from the p99 check (S15, S26, S27 real imperfect puns; N19, N30 invented links correctly blocked but scored as errors), 1 from a non-verbatim split quote (T3 quoted "her cat-nap"). Negatives: A 19/19, B 7/9, C 6/9, D 3/4, E 2/2 rejected; false alarms N02 (way→whey), N06, N08, N18 (morning→mourning). Fixes on `fix/soundalike-live-findings`: ignore `"": ""`, verify at p95, failed check → NON_PUN |
| **Live run after fixes** (`runs/20261023T180420Z`, published as `docs/evaluations/soundalike_after_fixes_20261023`) | same command | Binary 73/79 (92.4%), P 0.970, R 0.889, F1 0.928, decided 78/79; test texts 3/3 with correct mechanisms; negatives A 19/19, B 9/9, C 7/9, D 4/4, E 2/2; paired 31/36. Misses: S23 alleged, S27 tuna (0.875 < p95), S28 wok (model chose "fired"), S29 clothed; false alarm N06; N08 rejected for an invented `"extra"` key. N19/N30 blocked by the sound check (correct NON_PUN) |
| **Homograph regression** (`docs/evaluations/regression_{1,2}_20261023`) | 60-item corpus, two runs | Exact 52 and 54/60, binary 54 and 54/60 (October 4: 55 and 56/60). J22 lost in both runs with no soundalike input (likely the L4 prompt section); J06/J13/D09/D15 varied. Team decision: report as is (option A); gating the section was rejected because no local signal separates soundalike texts (finder fires on 9/36 positives; an exact-homophone gate opens on 34/60 homograph texts) |

**What this means.** Almost every positive depends on L4 naming the evoked
word itself (the finder only sees words already in the text), and imperfect
soundalikes below the p99 bar are guaranteed misses. An exact-homophone lookup
for every content word, or workstream 05, would supply most targets but adds
noise; decide after the live run.

## Planning-session checks (2026-10-19)

| Check | Command | Result |
|---|---|---|
| Heterographic items in `corpus/` | id prefixes + `heterograph\|homophone` grep over `corpus/*.jsonl` | **None**: project corpus `J/D/N` IDs; SemEval files `hom_` only |
| `scripts/prepare_semeval.py` heterographic option | grep | **Absent**: only `subtask*-homographic-test.*` |
| Gold label parsing | read `src/crack/corpus.py:126` | `gold_label` is parsed as `MainClassification`, so `VALID_SOUNDALIKE_JOKE` must exist first (03) |
| Always-pun F1 on SemEval het | arithmetic: P = 1271/1780, R = 1 | F1 = 0.833, consistent with design.md |
| "≥ 9 tokens OR Tom" F1 0.806, Tom 225/0 counts | none | **NOT run**; design.md's figure from the notes' archive analysis |
| Labeller agreement on negatives | none | **NOT run** (no labels yet) |

## Goal

Build the data and the scoring that show whether the extension works:

- ≥ 20 soundalike positives and ≥ 20 minimal-pair hard negatives (instructor
  requirement);
- a heterographic SemEval split;
- one evaluation script reporting the four levels in design.md § Evaluation plan;
- baselines that expose shortcuts.

## Files to create/modify

- Create `corpus/soundalike_blind.jsonl` (`id`, `text`, `target_ages`, as
  `load_blind` requires) and `corpus/soundalike_gold.jsonl` (the existing gold
  fields: `id`, `gold_label`, `genre`, `ambiguous_term`, `sense_a`, `sense_b`,
  `expected_age_verdict`).
- Create `corpus/soundalike_items.jsonl` holding the design's per-item metadata
  `{id, text, label, pair_id, neg_type, pun_word, target_word, mechanism}` plus
  a `slice` field (`seed`, `known_folk`, `test_text`). The three instructor test
  texts are their own slice and are not counted in the 20.
- Modify `scripts/prepare_semeval.py`: a heterographic option reading the
  `subtask{1,2,3}-heterographic-test.*` members of the same archive, writing
  `corpus/semeval_heterographic_{blind,gold}.jsonl`. The gold target lemma is
  the text before `%` in subtask 3's second sense key (e.g. `office%1:06:00::`).
- Create `scripts/evaluate_soundalike.py`.
- Create `tests/test_soundalike_data.py` (schema and integrity checks only).

## Interfaces

`scripts/evaluate_soundalike.py` levels (design.md):

| Level | Data | Metric | Baseline |
|---|---|---|---|
| P1 metric | six pairs, seed pairs, random pairs | six-pair ordering; ROC-AUC homophone/near vs random; binary-cost ablation | binary phone match |
| P2 finder | seed positives; SemEval het subtask 3 | Recall@k of gold target; mean alternates per item | k = 1 retrieval; last-word location |
| Detection | minimal pairs; SemEval het (or PunEval splits) | P/R/F1, balanced accuracy, **TNR per `neg_type`**, paired accuracy, coverage | always-pun; "≥ 9 tokens OR contains 'Tom'"; CRACK with phonetics off; LLM-only alternate |
| Regression | the 60-item project corpus | exact + binary accuracy | README October 4 pass must not drop |

Always report counts with percentages: with 29 positives, one item is about
3 points. Report SemEval with the Tom Swifty and "Old X never die" items split out.

## Acceptance tests

1. Data integrity: ≥ 20 positives and ≥ 20 negatives in the `seed` slice,
   counted after blind double labelling and dropping any item either labeller
   reads as wordplay. Every negative's `pair_id` names an existing positive;
   `neg_type ∈ {A, B, C, D, E}`; IDs are unique; blind/gold/items IDs match.
2. Every gold file loads with `crack.corpus` loaders (after 03 lands the enum).
3. The always-pun baseline on the prepared heterographic SemEval split prints
   F1 0.833 from 1,271 puns / 1,780 contexts. If the counts differ, stop and
   report.
4. The "≥ 9 tokens OR Tom" baseline is computed with a tokenisation written
   down in the script. Pin the observed F1 and compare it with design.md's 0.806.
5. The eval script runs fully offline on saved `records.jsonl` (rescoring, no
   provider calls).
6. Inter-annotator agreement (e.g. Cohen's κ on ≥ 50 items) is recorded next to
   the data.

## Depends on

The data files can start now. Gold loading needs [03](03_contract_l3_l4_l0post.md)
enums. Level P1 needs [01](01_phonetic_core.md), P2 needs
[02](02_soundalike_finder.md)/[05](05_lexicon_neighbours.md), and detection
needs 03.

## Open decisions

- Detection benchmark: SemEval het 1,780 vs the PunEval splits with no shared
  pun words vs PunBreak's 100 heterographic items.
- Gold label and gold mechanism for the three test texts (design.md flags
  drum/drama and cat-nap as ambiguous). Agree before running.
- The thresholds' dev/test split (team table: fit τ on a dev split).

## Risks

- SemEval heterographic detection is shortcut-prone; never report it without
  the baselines.
- Contamination: "folk" items are probably in LLM training data. Keep them a
  separate `known_folk` slice.
- 19 of the notes' 24 seed pairs are identical homophones, which leaves the
  graded metric barely tested. Keep the P26–P30 imperfect pairs.
- Type C/D negatives can be "almost puns" (Kao et al.), so labeller
  disagreement is expected.
- A detection or regression run is live and costs provider calls (NOT run).
- The SemEval archive is a network download; check its licence before
  committing derived files.
