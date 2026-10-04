# Full assignment: CRACK versus direct LLM

## Recommendation

For the current assignment, use the **direct full-analysis prompt with shared
AoA data and executable output checks** as the leading candidate for human review.
It produced better explanation and age evidence ratings and took about half the
time. Detection was close: one additional correct item, with the same paired
success. CRACK had higher precision. This comparison supports a practical choice
on this corpus; it does not show that every CRACK stage is unnecessary.

The direct solution analyzed the target, both readings, quotations, humor,
comprehension and content suitability. It was not the previous binary-only
SemEval baseline.

## Design

Both configurations used `gpt-6-luna`, the same 60 texts and 180 target-age
annotations, unchanged gold, the same frozen AoA CSV and lookup implementation,
and common field, target, quote and source-reference checks. Each input had its
own independent direct request. No labeled examples or corpus sentences were
included in the new prompts. CRACK retained its current source, native semantic
gates, candidate budget of 24 and thresholds. One fresh pass per configuration,
eight workers, with arm order fixed before inference: direct, then CRACK.

The direct model received a deterministic AoA table for input words and valid
literal compound parts. CRACK also queried words in its sense descriptions using
the same lookup function. Thus this compares complete configurations, including
their retrieval and age algorithms; it is not a pure causal test of layering.

The current runner calls L7/L8 without LLM clients: their results come from local
heuristics. These include taking low-AoA words from meaning descriptions,
estimating a secondary-sense offset, applying fixed metalinguistic floors and
scanning content keywords. Their numerical estimates are not measured acquisition
ages for the two senses.

## Detection, pairs and latency

| Metric | CRACK | Direct full-task LLM |
|---|---:|---:|
| Binary accuracy, all 60 | 55/60 (91.67%) | 56/60 (93.33%) |
| Precision | 92.00% | 88.89% |
| Recall, all 25 gold puns | 92.00% | 96.00% |
| F1, full gold | 92.00% | 92.31% |
| Decision coverage | 58/60 (96.67%) | 59/60 (98.33%) |
| Original + rewritten pair both correct | 21/25 (84.00%) | 21/25 (84.00%) |
| Ordinary controls correct | 10/10 | 10/10 |
| Mean complete-item latency | 35.26 s | 17.32 s |
| Fresh batch wall time | 278.42 s | 136.70 s |
| Observed SDK calls | 398 | 64 |
| Total recorded input + output tokens | 713,543 | 229,888 |

CRACK: TP 23, FP 2, TN 32, decided FN 1, one unresolved gold-positive and one
unresolved gold-negative. Direct: TP 24, FP 3, TN 32, no decided FN, one
gold-positive marked out of scope. Unresolved positives remain misses in the
full-gold recall/F1 denominators.

Both were correct on 54 items; CRACK alone on one, direct alone on two, neither
on three. The post-hoc exact paired McNemar p-value is 1.0. A one-item accuracy
difference does not establish a reliable detection advantage.

The frozen exact normalized target metric was 15/25 versus 21/25. It counts
`school` versus `schools`, for example, as different. A separate, post-hoc
WordNet morphology check gives **18/25 versus 24/25**. Neither metric proves
that an alternative target is wrong: CRACK's `together` in a `pull yourself
together` pun can be a useful analysis even when the annotated target is the
whole phrase. The blind evidence review evaluates contextual validity separately.

## Age labels and source support

| Subset / metric | CRACK | Direct full-task LLM |
|---|---:|---:|
| Project age-label matches, original puns | 49/75 (65.33%) | 61/75 (81.33%) |
| Assessed age labels, original puns | 69/75 | 75/75 |
| Matches on the same 22 correctly detected puns | 47/66 (71.21%) | 53/66 (80.30%) |
| All project age-label matches, including controls | 54/180 (30.00%) | 111/180 (61.67%) |
| All age-assessment coverage | 75/180 | 180/180 |
| Original-pun age explanations with verified numeric AoA references | 0/75 | 75/75 |

The all-text row includes literal-text assessments that current CRACK skips
after rejecting wordplay. The common-pun row compares the same texts and ages.
Direct's original-pun subset also includes its age assessment for the item it
marked out of scope; that is not a confirmed wordplay-age assessment.

These are **agreement with project labels**, not observed child comprehension.
Verified source entries support word-level vocabulary statements, not measured
acquisition of either sense or comprehension of the complete joke. The corpus
has no independent appropriateness gold. CRACK uses the AoA resource but its
current output does not link its age explanation to explicit source entries;
the adapter did not supply missing citations on its behalf.

## Anonymous LLM-assisted review

The reviewer saw matching-format A/B outputs, text, ages and the shared AoA
table. It received no system identities, corpus IDs, gold or aggregate metrics.
All 60 cases were reviewed in both A/B orders. Both systems were scored on the
same applicable dimensions. Missing analysis for an actual pun was scored rather
than excluded. Scores range from 0 to 2.

| Dimension | CRACK | Direct full-task LLM |
|---|---:|---:|
| Detection reasoning | 1.750 | 1.942 |
| Meanings and original-text evidence | 1.658 | 1.883 |
| Humor explanation | 1.579 | 1.877 |
| Age evidence | 0.000 | 1.965 |
| Appropriateness reasoning | 0.175 | 1.965 |

Both orders agreed on **34 direct preferences, 3 CRACK preferences and 4 ties**.
The remaining **19 cases changed preference with ordering** and remain separate.
The first two dimensions have 120 judgments per system; the last three have 57,
since the reviewer independently decided which texts involved in-scope wordplay.

The age scores indicate how the outputs justify their judgments under this
rubric. They are not independent age-validity measurements. The reviewer used
the same model family, and presentation can reveal implementation style even
when names are hidden. Its error flags are reviewer opinions, not verified
hallucination counts. **Independent human review is pending.**

## Validation correction and audit trail

The first frozen harness wrongly rejected faithful citations of `null / miss`
AoA entries. Those references accurately described absent data; the model had
not invented an age value. Before the repair, direct scored 54/60 and 19/25
pairs. CRACK's results were unchanged.

The generic repair accepts a reference only if all fields exactly match the
shared table. **Null remains unknown and earns no numeric-source credit.** All
saved replies were revalidated in chronological order, taking the first valid
reply. No prompt, gold label, threshold, quotation or age value was rewritten,
and no analysis inference was rerun. This recovered J21 and D11, and selected
the earlier valid answers for D18/D21 without changing their binary decisions.
Original records, original scores and the code diff are retained.

Both reviewer orders were repeated for all four changed cards. Two other
invalid-format reviews were also repeated, keeping the identical requests.
The final 120 valid reviews comprise 110 unchanged original reviews and 10 new
case/order reviews. None was chosen based on score or preference. Reported
latency and usage retain the original requests, including retries caused by
the validator bug; no faster counterfactual runtime is claimed.

An earlier display-only patch removed a system label from a generic failure
message before anonymous review. Its diff and original inference runner are
also preserved. It did not change analysis or scoring.

## Artifacts and reproduction

- [Fixed comparison protocol](../experiments/full_assignment/protocol.md)
- [Complete direct prompt](../experiments/full_assignment/direct_prompt.md)
- [Anonymous reviewer rubric](../experiments/full_assignment/judge_prompt.md)
- [Metric, configuration and hash summary](full_assignment_comparison_20261002.json)
- [Experiment instructions](../experiments/full_assignment/README.md)

Local run: `runs/full_assignment_comparison/20261003T021452.992281Z/` (UTC;
October 2 locally). Corrected results are in `corrected_validation/`. Both
directories retain source/resource snapshots, raw API responses, request IDs,
timings and manifests. Human-review materials are in
`corrected_validation/blind_review/packets.html`, `rubric.md` and
`human_ratings.csv`. Do not open `identity_key.json` before rating.

```bash
.venv/bin/python scripts/compare_full_assignment.py \
  --model gpt-6-luna --concurrency 8 --with-judge
```

The current harness includes the generic null-reference correction. To reproduce
the completed run's arithmetic without API calls:

```bash
.venv/bin/python \
  runs/full_assignment_comparison/20261003T021452.992281Z/corrected_validation/runner.py \
  --run runs/full_assignment_comparison/20261003T021452.992281Z/corrected_validation \
  --worker score
```

The experiment changes no production pipeline behavior. To investigate which
layers contribute, a separate controlled ablation is needed; this complete-task
comparison alone cannot assign the differences to L3, L4, L5 or L6.
