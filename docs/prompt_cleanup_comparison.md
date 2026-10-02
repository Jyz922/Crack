# Prompt example cleanup and controlled comparison

The production templates use abstract assessment rules and the response schema.
Concrete evaluation sentences and illustrated word/meaning answers were removed
from L5 QA, L5 declarative and L6. L4 had already been cleaned before this change.
No replacement classic jokes were inserted.

## What changed

| Template | Removed | Replacement |
|---|---|---|
| L5 QA | The library/stories/floors example and illustrated pairs of semantic domains | Describe contextual contrast and whether the answer actually exploits both readings |
| L5 declarative | The fishermen/net-loss sentence and repeated-word example phrases | Describe single-occurrence and repeated-occurrence requirements without named words |
| L6 | Named trunk and run meaning pairs | Describe materially different interpretations versus minor facets of the same meaning |

The scoring dimensions, numeric guidance, thresholds, response fields and gold
labels are unchanged. Exact source-quote validation and the single corrective
L4 retry are unchanged. Failed evidence is never silently rewritten into an
accepted result.

## Shared L4 format clarification

An initial control run completed 60 items but none reached L5 or L6: L4 replies
frequently supplied a meaning description in `resolving_sense`, instead of the
required string identifier. Its 20 execution failures and other findings remain
in the local run evidence. The incomplete treatment arm was interrupted and is
excluded from the comparison of cleanup effects.

The existing L4 contract was then stated more explicitly in the prompt:
`resolving_sense` is a field reference with permitted JSON values
`"sense_a"`, `"sense_b"` or `null`, never the meaning text. No acceptance rule
changed. Three fixed development cases produced valid findings on their first
attempt (two PASS, one ONE_SENSE_ONLY). This checks format compliance on those
cases, rather than establishing overall accuracy.

Both arms of the new comparison share this same clarification. The changed
templates between arms are still only L5 QA, L5 declarative and L6. The earlier
control result is not mixed with these new paired results.

## Fixed development examples

[Prompt development v1](../corpus/prompt_development/v1/README.md) contains ten
project-authored examples with readings, expected findings, family IDs and
annotation notes. The texts and annotations are frozen by a SHA-256 manifest.
They are separate from evaluation inputs and are not inserted into production
requests. Development examples can be inspected when drafting rules; they do
not provide independent benchmark scores.

## Overlap audit

```bash
python scripts/audit_prompt_overlap.py
```

The audit compares static templates and development texts against all available
evaluation blind files under `corpus/`. Dataset aliases and subsets may contain
the same records. The `prompt_development/` inputs are excluded from evaluation
references and audited separately as development subjects. It normalizes case
and punctuation for this audit only;
production source-quote validation remains exact and case-sensitive.

- A complete input sentence of at least six tokens or an eight-token matching
  phrase fails the audit.
- Six/seven-token matching phrases and quoted target words produce review hints.
  Shared vocabulary alone is not rejected.
- Paraphrases, common joke families and supplied word/meaning answer pairs need
  manual review. Passing these checks does not establish freedom from model
  training contamination or prior developer exposure to evaluation items.

The saved local audit has one long match and thirteen review hints before
cleanup, and no matches or hints after cleanup. The named trunk/run answer
examples were removed after manual inspection even though word overlap alone
is not an automatic failure.

## Prompt-only comparison

The saved paired arms ran the response-contract version-3 pipeline. They differ
only in the three prompt templates listed above. The historical version-2 run
is preserved separately and is not the control arm for this experiment.

The comparison script creates two source snapshots before inference, records
prompt/code/input/gold/resource hashes and settings, and checks their identity
against each completed run. Both use fresh inference; no old predictions are
resumed. All non-prompt pipeline source is identical between arms. Settings are
recorded without API keys. Gold is passed only to the evaluator.

The current pipeline subsequently moved to contract version 4; see the
[constraint review](constraint_review.md). A new comparison using current code
records that version in both arms. Reproducing the historical scores requires
the original frozen source and prompt snapshots, not current source with old
prompts. The results below remain the saved version-3 observations.

Local before-cleanup templates with the shared L4 clarification are retained in
`runs/prompt_cleanup_ablation/before_prompts_enum_guidance/`. This directory is local run
evidence and is excluded from production loading and the overlap audit. Given
that snapshot (or another saved prompt version), reproduce the comparison with:

```bash
python scripts/compare_prompt_versions.py \
  --before-prompts runs/prompt_cleanup_ablation/before_prompts_enum_guidance \
  --after-prompts src/crack/prompts \
  --backend openai --concurrency 4 --repeats 1
```

Add `--prepare-only` to freeze the experiment without making provider requests.
Each invocation creates a new output directory and refuses to overwrite an
existing one. `--repeats` runs complete pairs and alternates arm order; all
pairs remain in the report rather than selecting the best result.

The report includes all-item accuracy, decided-item accuracy, coverage,
age-assessment coverage, failure/abstention counts and every changed prediction.
Provider variation remains possible even with identical model settings. A
single paired run describes observed behavior; repeated comparisons and an
independent unseen dataset are needed for broader conclusions.

## Results

Both arms completed all 60 inputs, with no missing predictions or records from
an older response contract. Backend: `openai`; requested model: `gpt-6-luna`;
concurrency: 4. Only the three cleanup templates differ between arms.

| Metric | Before cleanup | After cleanup |
|---|---:|---:|
| Exact-label accuracy, all items | 31/60 (51.67%) | 29/60 (48.33%) |
| Binary detection accuracy, all items | 31/60 (51.67%) | 31/60 (51.67%) |
| Decision coverage | 39/60 (65.00%) | 37/60 (61.67%) |
| Exact-label accuracy, decided items | 31/39 (79.49%) | 29/37 (78.38%) |
| Binary detection accuracy, decided items | 31/39 (79.49%) | 31/37 (83.78%) |
| Binary F1, decided items | 81.82% | 85.00% |
| False positives, decided items | 3 | 1 |
| False negatives, decided items | 5 | 5 |
| Insufficient evidence | 20 | 22 |
| Execution failures | 1 | 1 |
| Age-assessment coverage | 63/180 (35.00%) | 54/180 (30.00%) |
| Age-label agreement, assessed labels | 46/63 (73.02%) | 38/54 (70.37%) |

All-item binary accuracy is unchanged. Exact-label accuracy fell by 3.33
percentage points and coverage fell by 3.33 points. The higher decided-item
binary accuracy accompanies fewer decisions; this run does not establish an
overall performance improvement.

Thirteen final labels changed. Twelve of those cases already differed in their
L4 status, although both arms used the same L4 prompt. L1 and L2 outputs were
identical for all 60 paired inputs. Thus the observed final differences include
variation in an unchanged upstream model stage; they cannot all be attributed
to the L5/L6 cleanup.

Most unresolved findings concern the candidate search budget: 18 cases before
and 19 after had untested retrieved terms beyond top-k. In the after arm, the
other three unresolved cases require contextual assessment. The single after-arm
execution failure was a persistent nonverbatim source quote; it was rejected
after the permitted correction rather than accepted or converted into a negative.

The originally highlighted D03 remains a positive prediction in both arms,
despite its negative gold label. J24 changed from positive to negative at L4;
its outcome does not demonstrate that deleting an L5 example caused the change.
J23 and D23 both remained negative. These observations do not support the prior
claim that example overlap was proven to be the direct cause of those errors.

[The machine-readable report](prompt_cleanup_results.json) includes complete
evaluation summaries, configuration/resource/source hashes, every changed label,
uncertainty and execution-failure reasons, and the interrupted initial experiment.
Raw paired predictions, prompts and API traces remain in the local
`runs/prompt_cleanup_ablation/` evidence directory. The historical benchmark
claims are not replaced with a selected conditional score from this comparison.
