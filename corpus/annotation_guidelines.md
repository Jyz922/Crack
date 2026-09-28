# DoubleTake Humor & Wordplay Annotation Guidelines

## 1. Overview

The DoubleTake evaluation corpus consists of paired JSON Lines files designed for reproducible benchmarking of age-aware homograph humor detection:

- `joke_corpus_blind.jsonl`: Inputs available to the pipeline (`id`, `text`, `target_ages`).
- `joke_corpus_gold.jsonl`: Ground-truth linguistic annotations (`id`, `gold_label`, `genre`, `ambiguous_term`, `sense_a`, `sense_b`, `expected_age_verdict`).

## 2. Corpus Composition (50 items)

| Group | IDs | Count | Description |
|---|---|---:|---|
| **Positive Jokes** | `J01`–`J20` | 20 | Valid homograph and compound-split jokes across all 4 genres |
| **De-joked Controls** | `D01`–`D20` | 20 | Lexically and syntactically matched negative controls removing the double meaning |
| **Ordinary Non-Jokes** | `N01`–`N06` | 6 | Everyday sentences containing ambiguous words with only one sense active |
| **Out-of-Scope Controls** | `O01`–`O04` | 4 | Homophone puns (heterographic) and situational non-lexical jokes |
| **Total** | | **50** | Benchmark evaluation corpus |

## 3. Classification Taxonomy (`gold_label`)

1. `VALID_HOMOGRAPH_JOKE`:
   - Text creates humor through homographic ambiguity (identical spelling, two distinct active meanings).
2. `VALID_COMPOUND_SPLIT_JOKE`:
   - Text creates humor through compound resegmentation (e.g., *autobiography* = *auto + biography*, *mushroom* = *mush + room*).
3. `ONE_SENSE_ONLY`:
   - An ambiguous word is present, but context activates only one meaning (e.g., ordinary sentences or de-joked texts).
4. `RESOLUTION_FAIL`:
   - Two meanings may be mentioned, but the punchline does not logically contrast or resolve the question/setup.
5. `OUT_OF_SCOPE_HOMOPHONE`:
   - Wordplay relying on heterographic homophones (sound alike, spelled differently, e.g., *knight* / *night*, *flour* / *flower*).
6. `OUT_OF_SCOPE_NONLEXICAL_JOKE`:
   - Jokes relying on absurd situations, slapstick, or cultural references without lexical ambiguity.

## 4. Text Genres (`genre`)

- `QA_RIDDLE`: Setup as question, resolution in answer punchline ("Why do elephants have a trunk? ...").
- `DEFINITIONAL_ONELINER`: Dictionary-entry or declarative definition style ("Autobiography: when your car...").
- `DIALOGUE_MISUNDERSTANDING`: Two or more speakers talking with misaligned senses.
- `DECLARATIVE`: Statement joke in narrative sentence format.

## 5. Age Appropriateness Standards

Age ratings follow the Brysbaert Age-of-Acquisition (AoA) norms and cognitive development milestones:

- `FULLY_AGE_APPROPRIATE`: Child knows both senses and has metalinguistic awareness for the joke structure.
- `PARTIALLY_COMPREHENSIBLE`: Child knows the primary surface sense but the secondary figurative sense is above their AoA.
- `VOCABULARY_TOO_ADVANCED`: The ambiguous term or secondary sense requires an older vocabulary level.
- `WORDPLAY_SKILL_TOO_ADVANCED`: The vocabulary is known, but the metalinguistic resegmentation floor has not been met (e.g., age 6 facing compound split).
