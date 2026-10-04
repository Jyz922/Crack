# Corpus repair review

Historical repair review. Candidate continuation described below is retired;
current behavior stops after failed/unknown semantic stages. See
[response validation](response_validation.md) and
[the failure/retry/fallback policy](provider_failure_policy.md).

The proposed repair plan is partly supported by the saved version-2 run.
The changes below address reusable failure modes. No corpus text, label, item ID,
QA threshold or scoring weight was added to the production decision rules.
The blind and gold corpus files remain unchanged.

## Decisions on the proposed repairs

| Proposal | Decision and implementation |
|---|---|
| Normalize failed source quotes | Keep exact, case-sensitive source quotes. Allow one L4 corrective request with the validation error; preserve both raw attempts. Never convert a guessed quote into accepted evidence. |
| Permit shorter split parts | Permit two-letter parts only when both are exact WordNet lemmas. A dictionary split is a proposal, not proof of wordplay or of a prefix meaning. |
| Prefer splits or retain both paths | Retain all split options within the term's L3 entry. Let contextual evidence select the mechanism; do not prefer split labels by corpus genre or gold label. |
| Reject target drift | Require an exact `target_term` and validate the selected split pair. Keep the selected candidate aligned with L5/L6 and the report. Declared target identity alone cannot verify meaning identity. |
| Improve candidate fallback | Preserve the existing search through later candidates until PASS. Save every candidate attempt. Return uncertainty if all tested candidates are single-sense but other retrieved terms remain untested. |
| Lower the zero-frequency score | Keep the existing ranking formula and weights. Record `balance_observed` so 0/0 is visible as unobserved usage. A proposed scoring change displaced a rare lexical candidate in an offline regression; it needs independent ranking evaluation. |
| Add failing examples and raise QA thresholds | Use general instructions about syntax, modifiers, referents and contextual evidence. Keep QA thresholds and component floors unchanged pending independent calibration. |

WordNet retrieval now uses a shared lock around local reader operations, including
lazy initialization. This addresses concurrent access to the reader's shared
file cursors. Model requests remain concurrent after lexical retrieval.

## What the saved errors establish

- **J03:** the saved trace establishes a rejected nonverbatim quote. The original
  response is absent, so a punctuation-only explanation is unverified. New logs
  preserve this evidence.
- **J06:** the supplied split proposals omitted a short part. Allowing two-letter
  dictionary parts fixes the search restriction, but WordNet's meanings of `ex`
  do not automatically establish the intended prefix meaning “out”. Prefix
  semantics require an appropriate lexical source and contextual evidence.
- **J13:** retaining split options fixes information loss during deduplication.
  The intended `mushroom` / `much room` reading may also require a sound
  substitution. The supplied `mush + room` split cannot establish it on its own.
- **J21:** L4 already tried later candidates before saving its first negative.
  Without per-candidate responses, the saved record cannot show what happened
  during the `bark` assessment. Changing the displayed fallback word alone would
  not establish a detection improvement.
- **J24:** meanings of `stories` were attached to candidate `many`. Explicit target
  identity improves this contract and makes declared drift rejectable. Semantic
  drift can still survive an echoed target and must be evaluated separately.
- **D03:** the repeated `trunk` contexts can support animal and car readings. Its
  negative label warrants independent review; repetition must not be prohibited
  merely to reproduce that label.
- **D10:** dictionary meanings alone do not establish an educational reading in a
  factual description of fish groups. Require contextual support for each reading.
- **D17:** `metal mail carrier sack` is grammatically awkward and may invite multiple
  parses. Review the text and annotation independently before attributing every
  disagreement to a model hallucination.

Gold-label disagreements remain in the baseline. Annotation review should be
performed independently of predictions and preserve the original label version.
If a new annotation version is published, evaluate both systems against that
same version and retain results for the original labels.

## Frozen baseline

The local run `runs/20261001T151602Z` used response contract version 2:

| Metric | Result |
|---|---:|
| Exact-label accuracy, all items | 51/60 (85.00%) |
| Decision coverage | 58/60 (96.67%) |
| Exact-label accuracy, decided items | 51/58 (87.93%) |
| Binary accuracy, all items | 53/60 (88.33%) |
| Binary accuracy, decided items | 53/58 (91.38%) |
| Binary F1, decided items | 89.36% |
| Age-label agreement, all labels | 51/180 (28.33%) |
| Age-assessment coverage | 72/180 (40.00%) |
| Age-label agreement, assessed labels | 51/72 (70.83%) |

The last two rows come from offline rescoring of the same saved predictions;
no new model calls were made. They explain the denominator of the old age
metric. They do not establish improved age prediction. The age heuristic still
needs separate evaluation of vocabulary across the whole text, required
background knowledge and inference complexity.

[The baseline manifest](validation_v2_baseline.json) records SHA-256 hashes of
the source run files and the current blind/gold corpus. Run files remain local.
The historical run metadata records a Git SHA and a limited configuration;
it does not reconstruct all uncommitted source or provider settings.

## Evaluation without fitting to these 60 texts

1. Treat these 60 inspected items as a development and audit set. A fresh run
   measures repair effects on this set; it does not establish unseen accuracy.
2. Freeze code, prompt, configuration, lexical resources and annotations before
   the next comparison. New runs automatically save source/prompt and blind-input
   hashes plus nonsecret settings before inference. Preserve gold and resource
   hashes alongside the evaluation.
3. Collect an independent evaluation set that has not been inspected while
   developing these repairs. Keep a joke and its rewritten control, shared joke
   templates and close paraphrases in the same split. Resplitting the inspected
   60 cannot make them unseen again.
4. Compare the frozen old and new systems using the same inputs, provider/model
   configuration and annotation version. Repeat complete runs to measure model
   variation; include every run rather than selecting the best one.
5. Report exact and binary all-item accuracy, decided-item accuracy and coverage
   together. Report abstentions and failures separately, with age-assessment
   coverage. A higher decided-item accuracy with fewer decisions needs both
   denominators to interpret it.
6. Calibrate any future ranking weights, QA thresholds or agent/causal floors on
   a separate development split. Choose them before viewing held-out results.

## Run the repaired pipeline

The following performs fresh API inference for the current corpus. It does not
resume or overwrite the version-2 baseline:

```bash
source .venv/bin/activate
crack --input corpus/joke_corpus_blind.jsonl \
  --eval corpus/joke_corpus_gold.jsonl \
  --output runs/corpus_validation_v4.jsonl \
  --backend openai --concurrency 4
```

New predictions use response contract version 4. No new accuracy claim is made
until this inference run completes. The stricter incomplete-search policy can
increase abstentions; inspect coverage alongside accuracy.

The [constraint review](constraint_review.md) records the subsequent bounded
identifier normalization and clarification of what the L6 ablation assesses.
