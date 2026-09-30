# Project-Curated Wordplay Corpus: Annotation Notes

## Purpose and files

This 60-item corpus is a small, project-curated evaluation set for English wordplay classification and age-comprehension estimates. It is not an official benchmark or a representative sample of English humor.

- `joke_corpus_blind.jsonl` contains the input text and requested target ages.
- `joke_corpus_gold.jsonl` contains the project's labels, genre, ambiguous term, sense notes, and expected comprehension status by age.

## Composition

| Group | IDs | Count | Gold label |
|---|---|---:|---|
| Wordplay examples | `J01`–`J25` | 25 | 21 `VALID_HOMOGRAPH_JOKE`; 4 `VALID_COMPOUND_SPLIT_JOKE` |
| De-joked controls | `D01`–`D25` | 25 | `ONE_SENSE_ONLY` |
| Ordinary statements | `N01`–`N10` | 10 | `ONE_SENSE_ONLY` |
| **Total** | | **60** | |

## Classification labels

- `VALID_HOMOGRAPH_JOKE`: the text uses one spelling with two contextually active meanings.
- `VALID_COMPOUND_SPLIT_JOKE`: the wordplay depends on resegmenting a written compound.
- `ONE_SENSE_ONLY`: the text does not activate two distinct meanings as wordplay.

The current corpus uses these three labels. Other labels in the pipeline schema are not used as gold labels here.

## Genres

- `QA_RIDDLE`: question followed by an answer punchline.
- `DEFINITIONAL_ONELINER`: a definition-like setup or one-line explanation.
- `DIALOGUE_MISUNDERSTANDING`: a word or phrase is interpreted differently across speakers.
- `DECLARATIVE`: wordplay embedded in a statement.

## Age-comprehension annotations

`expected_age_verdict` records the expected **comprehension** status for each age in `target_ages`; it is not the L8 content-safety verdict.

- `FULLY_COMPREHENSIBLE`: both relevant readings and the wordplay structure are expected to be understandable.
- `PARTIALLY_COMPREHENSIBLE`: the main reading may be understood, while the secondary reading or wordplay may not be.
- `SENSE_B_TOO_ADVANCED`: the secondary sense is expected to be too advanced.
- `WORDPLAY_SKILL_TOO_ADVANCED`: the vocabulary may be familiar, but the wordplay operation is expected to be too advanced.
- `AOA_UNKNOWN`: available AoA information is insufficient for an estimate.

These age labels are project annotations informed by AoA values and curator judgment. The evaluation's age-label match rate is measured against these annotations.

## Current evaluation

The complete run on the current 60-item corpus, dated 2026-09-30, achieved 56/60 exact-label accuracy (93.33%). For binary pun detection, the two `VALID_*_JOKE` labels count as positive: precision 89.29%, recall 100.00%, and F1 94.34%. Age-comprehension outputs matched 142/180 project annotations (78.89%).

The [per-item records](../runs/course_corpus_records.jsonl) and [evaluation summary](../runs/course_corpus_eval.json) contain the full results. The earlier 53/60 result was superseded after a fresh run on the current texts; see the [benchmark audit](../docs/benchmark_audit.md) for the record history.
