# Review of the proposed constraint relaxations

Historical review of the earlier continuation/ablation implementation. Current
runtime behavior is specified in [response validation](response_validation.md)
and [the failure policy](provider_failure_policy.md); no continuation or
controlled-rewrite gate remains in the October 4 design.

## Decision

Adopt bounded formatting tolerance for the candidate identifier and clarify the
L6 ablation question. Keep exact source evidence, supplied literal segmentations,
and the distinction between an incomplete search and a negative decision.
Continue the candidate-search repair already implemented before this review.

The proposal identifies a real search-coverage problem, but its five-rule causal
explanation is not established by the saved results. No new accuracy result is
claimed for this review's changes.

## Evidence checked

The complete paired runs are preserved locally at:

- `runs/prompt_cleanup_ablation/paired_enum_guidance/pair_01/before/runs/20261002T045321Z/`
- `runs/prompt_cleanup_ablation/paired_enum_guidance/pair_01/after/runs/20261002T050014Z/`

Each arm contains 60 records. The historical version-2 score of 51/60 (85%) is
not the control for this prompt-only comparison. Both paired arms use contract
version 3 and differ in three prompt templates; their unchanged L4 stage also
produced different responses. The observed exact-label change is 31/60 to
29/60, while all-item binary accuracy remains 31/60 in both arms.

| Saved observation | Before cleanup | After cleanup |
|---|---:|---:|
| Search-limit insufficient-evidence items | 18 | 19 |
| Of those, negative gold labels | 17 | 17 |
| Of those, positive gold labels | 1 | 2 |
| Other insufficient-evidence items | 2 | 3 |
| Execution failures | 1 | 1 |
| Target spelling/case mismatches in saved parsed L4 attempts | 0 | 0 |
| L6 distinctness passes with SUPPORTED ablation | 21 | 18 |
| L6 SENSES_DISTINCT findings blocked only by ablation | 0 | 0 |

Thus the proposal's claim of 19 known-correct negatives is inaccurate. Converting
all 19 search-limited findings to negatives would include two positive examples.
These counts describe gold labels, not predictions of what a completed search
would find. Completing the search still requires fresh inference.

The maximum retrieved candidate-term count in each saved arm is 13. The current
default L4 budget is 24, and L3 now retains its tail. That continuation change
postdates these paired runs; the old 48.33% exact-label result does not evaluate
the current search implementation. Retrieved terms are lexical proposals after
filtering/deduplication, not every token, pronoun or function word in the input.

## Review by proposal

| Proposal | Assessment | Action |
|---|---|---|
| Treat top-k single-sense findings as a whole-text negative | A ranked shortlist can omit the wordplay site. The existing search-completion repair addresses the observed budget issue without converting unassessed evidence to a negative. | Keep tail continuation, budget 24, search accounting and explicit uncertainty when the search remains incomplete. |
| Normalize or loosely align source quotes | The J03 record establishes a failed quote check but does not retain the raw quote, so a punctuation-only cause cannot be established. The after-arm D08 rejection includes a capitalized reconstructed context. Quote tolerance is not demonstrated to explain the large accuracy gap. | Keep verbatim quotes and the existing one corrective request. Do not activate `_align_substring` in production. This also preserves the user's prior requirement against automatically making failed evidence valid. |
| Ignore case in `target_term` | Case and surrounding whitespace can be harmless identifier formatting. Changing an inflection or spelling is a different operation and can change the candidate. No such formatting mismatch occurs in these saved paired records. | Accept only `strip().casefold()` equivalence, then use the supplied identifier downstream. Preserve the raw/parsed response; do not change source quotes, meanings or verdicts. |
| Accept arbitrary or near-sounding `split_parts` | A sound substitution is a new mechanism, not a literal segmentation of the supplied spelling. Broadening that mechanism needs a separate proposal/retrieval/validation and evaluation design. | Keep the supplied segmentation constraint. Do not add exceptions from individual evaluation items or change gold labels. |
| Override UNSUPPORTED ablation using confidence | The after arm has no L6 ablation-only rejection. A model resolution score is not calibrated evidence that an incomplete ablation should pass. The prompt's `pun/humor` wording is ambiguous about unrelated humor. | Clarify that only the claimed two-meaning wordplay must disappear. Require a controlled substitution and explain the lost/retained contrast. Keep the completed-ablation gate. |

The retained ablation is a model judgment, not an independently rerun experiment.
Local format checks do not validate its semantic conclusion. Any future decision
to remove that gate should use a separately frozen comparison, including false
positives and coverage, rather than promote an unsupported result by score alone.

## Implemented changes

- Response contract version 4 allows bounded target-identifier formatting.
  Validation returns a copy with the supplied identifier, leaving the original
  response available in `l4_attempts`.
- The L4 instructions distinguish identifier formatting from spelling changes
  and exact evidence quotation.
- The L6 instructions ask whether the two-meaning contrast disappears while
  preserving the surrounding situation; unrelated humor may remain.
- The comparison script reads the current contract version and checks it
  against each run instead of hard-coding version 3.
- Documentation distinguishes historical version-3 results from future runs.

The pre-change source snapshot and input/gold hashes are saved locally under
`runs/constraint_review/20261002T170054Z/`. Ranking, numeric thresholds, search
budget, final decision gates, source-quote validation, corpus texts, gold labels
and the fixed development examples are unchanged by this review.

## Evaluation plan

Freeze rules before evaluation. Use the fixed development set for further rule
drafting, without adding evaluation sentences or answer pairs to production
prompts. The inspected 60-item corpus is a regression set; use an independent
unseen set for generalization claims.

Compare formatting tolerance and ablation wording as separate changes. For the
L6 wording comparison, reuse one fixed collection of L1-L5 results in both arms
so upstream model variation does not obscure the treatment. Compare candidate
budgets separately. Report all-item accuracy, decided-item accuracy, coverage,
false positives/negatives, execution failures and search termination counts;
retain all repeated runs rather than select the best score.

This review checked saved evidence, syntax and unchanged-file hashes. It did not
run tests or make new model requests. Fresh version-4 inference is required for
a current end-to-end score; historical predictions are not relabeled as new
results.
