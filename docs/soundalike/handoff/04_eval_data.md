# 04 — Evaluation data, heterographic SemEval, eval script, baselines
Last updated: 2026-10-19 by soundalike docs-planning session (offline, no code written)

Status: **not started**. Back to [HANDOFF](../HANDOFF.md).

## Checks this session

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
