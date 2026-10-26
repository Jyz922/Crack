# October 25 resource refresh: user live reruns

Subsequent execution and scoring changes are recorded in
[Engineering fixes](engineering_fixes_20261025.md). The results below describe
the saved pre-fix runs and have not been replaced by a new inference run.

Both runs completed on October 25 in America/Indiana/Indianapolis. Their
directory timestamps use UTC October 26. They use OpenAI `gpt-6-luna`, the
same prompt templates, concurrency 8, and candidate budget 8, with OEWN 2025
and the pinned official CMUdict snapshot. Source hashes and resource checksums
identify the working tree; its Git HEAD still points to the pre-refresh base.

| Metric | Soundalike before refresh | Soundalike after refresh | Regression before refresh, runs 1 / 2 | Regression after refresh |
|---|---:|---:|---:|---:|
| Exact classification | 71/79 (89.9%) | 67/79 (84.8%) | 52/60 / 54/60 | 51/60 (85.0%) |
| Binary correct, all items | 73/79 (92.4%) | 71/79 (89.9%) | 54/60 / 54/60 | 53/60 (88.3%) |
| Decision coverage | 78/79 | 79/79 | 59/60 / 58/60 | 59/60 |
| Execution failures | 1 | 0 | 1 / 2 | 1 |

After-refresh soundalike counts: TP 32, FP 4, TN 39, FN 4. Precision, recall and
F1 are each 0.8889. After-refresh regression counts: TP 22, FP 4, TN 31, FN 2,
plus one unresolved positive due to execution failure. Its decided-item
precision/recall/F1 are 0.8462/0.9167/0.8800. The all-item accuracy denominator
retains that failed item.

## Soundalike findings

- Four positives are missed: S15 (tents), S23 (alleged), S27 (tuna), and T3
  (cat-nap). S27 is still blocked by the phonetic threshold. T3 fails L5 at
  0.4575 versus the unchanged QA threshold 0.46, with an explanation that the
  proposed readings overlap.
- Four negatives are predicted as puns under the authored reference labels:
  N06, N18, N19 and TN2. TN2 treats literal cat/cad co-occurrence as sufficient
  sound-based wordplay. N18 and N19 also deserve independent label review:
  undertaker/morning and nervous/two tents can plausibly evoke alternate frames.
- S28 and S29 now receive positive binary decisions but are labeled homograph
  jokes rather than the annotated soundalike mechanism. N13 and N30 receive
  ANCHORING_FAIL rather than ONE_SENSE_ONLY; these are correct binary rejections
  but exact-label mismatches. This explains the additional gap between binary
  and detailed classification scores.
- T1 and T2 pass. T2 still introduces a weakly supported legal-suing reading.
  T3 fails. Do not report all three instructor interpretations as correct.

## Regression findings

The single execution failure is **J21**, "We couldn't imagine making a dog from
wood bark." L4 returned an additional `unused` field. The exact-key validator
rejected it. This is a response-contract failure, not an API-key or dictionary
loading failure, and it must remain separate from semantic negatives.

The two false negatives are J06 (explain) and J22 (skip). J22 was also missed
in both October 23 runs. J06 varied between those runs. The four reference-label
false positives are D01, D03, D17 and D24. D03, D17 and D24 were already false
positives in both earlier runs. D01 is a new false positive relative to those
two runs, treating literal muscles and physical strength as sufficient wordplay.

J13 is a positive binary decision with a soundalike label instead of its
compound-split annotation. N01 is a correct binary rejection with
RESOLUTION_FAIL rather than ONE_SENSE_ONLY. Together they account for the two
additional detailed-label mismatches beyond the seven all-item binary errors.

For age assessment, agreement across all 75 labels on annotated puns is 46/75
(61.3%), with 63/75 assessed and assessed-label agreement 46/63 (73.0%). The
original 53/180 metric includes literal controls that the pipeline generally
does not age-assess. Keep that denominator visible, but do not describe it as
accuracy measured on children. All age references are curator annotations.

## Interpretation and evidence

Both observed all-item binary scores are below the older runs. These single
stochastic reruns do not isolate a causal dictionary effect or establish a
statistically reliable regression. They provide no evidence for claiming an
accuracy improvement from the resource refresh. Several errors recur across
versions, and several authored labels have arguable semantic boundaries.

Prioritize independent label review and a separate development set before
changing prompts or thresholds. A controlled resource comparison should hold
model settings and prompts fixed, retain all runs, and inspect predictions
alongside shortlist changes. No prompts, thresholds or labels were changed
in response to these scores.

Compact records, metadata and checksum manifests are retained locally in:

- [Soundalike rerun](evaluations/resource_refresh_soundalike_20261025/evaluation.json)
- [Regression rerun](evaluations/resource_refresh_regression_20261025/evaluation.json)

The original raw records remain in their `runs/` directories. Compact copies
omit raw attempts and L2 payloads as declared in their manifests. Offline
rescoring reproduces every original summary metric; this validates arithmetic
and local contracts, not the correctness of model interpretations.
