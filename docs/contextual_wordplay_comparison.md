# Contextual wordplay: L6 clarification experiment

## Decision

**Keep the current production L6 prompt.** The contextual clarification improved
rejection of incidental second-domain cues in new stage cases, but lost intended
positive cases and regressed on the unchanged course corpus. It failed the
acceptance criteria frozen before inference. The experimental prompt, cases and
all results are retained; no runtime threshold, gold or age algorithm changed.

## What was examined

L6's existing rewrite test could credit removal of a dictionary association
without establishing that the original wording used it as wordplay. The draft
requires an original cue-to-reading interaction before crediting ablation, and
asks the model to distinguish incidental nearby objects from a misunderstanding,
reply, comparison or lexical double-take. The rule is abstract: it includes no
course sentences, target-word answers or per-item exceptions.

Only the L6 template differs. Both arms use `gpt-6-luna`, the same field/quote
validators, L4/L5 prompts, settings, 24-candidate budget, continuation policy,
WordNet/AoA resources and age algorithms. The broader rule requiring mutual
suppression of senses was not changed in this experiment.

## New stage cases

Twenty-four newly authored cases were frozen by hash before inference. Six word
families provide 12 development cases; six other families provide 12
confirmation cases. Each contains an intended pun and a literal control with an
incidental second-domain cue. Both models receive the same target, proposed
senses and quotes, without annotations. Neither dataset is inserted into
production prompts. There was one frozen draft and one pass per arm.

| Split / finding | Baseline | Contextual draft |
|---|---:|---:|
| Development: intended positives passed | 6/6 | 6/6 |
| Development: literal controls falsely passed | 6/6 | 2/6 |
| Confirmation: intended positives passed | 6/6 | 4/6 |
| Confirmation: literal controls falsely passed | 6/6 | 0/6 |
| Stage execution / response-contract failures | 0 | 0 |

The draft withheld support for the carpenter/beam and mediator/resolution
confirmation cases. These are misses against the frozen development
expectations, which are provisional project annotations awaiting human review.
No labels were changed after observing the outputs. The development cases about
`seal` and `strike` still falsely passed. Thus this does not establish complete
control of contextual hallucinations.

These are **L6 results given proposed readings**, not end-to-end CRACK accuracy.
The model was deliberately given both hypotheses even for literal controls;
that makes this a targeted challenge to the final check. The cases are synthetic
and structurally related within pairs. The confirmation families were separate
and not used for revisions in this experiment; after this run they are available
for regression inspection, not a new untouched benchmark.

## Current 60-item corpus

The baseline exactly reproduced all 60 previous substantive outputs and all
409 saved SDK calls, with zero new requests. Treatment reused a reply only for
an identical per-item stage/request, at most once. Changed L6 calls and new
search branches used fresh inference. Both gold and all texts/ages are unchanged.

| Metric | Current production policy | Contextual draft |
|---|---:|---:|
| Binary accuracy, all texts | 55/60 (91.67%) | 53/60 (88.33%) |
| Precision | 88.46% | 88.00% |
| Recall, all gold puns | 92.00% | 88.00% |
| F1, full gold | 90.20% | 88.00% |
| Decision coverage | 59/60 (98.33%) | 57/60 (95.00%) |
| Original + rewrite both correct | 21/25 | 19/25 |
| Exact normalized target matches | 15/25 | 15/25 |
| Common assignment-output contract failures | 0 | 0 |
| New SDK calls in this corpus intervention | 0 | 44 |
| New input + output tokens | 0 | 87,386 |

The baseline has TP 23, FP 3, TN 32, decided FN 1 and one unresolved positive.
Treatment has TP 22, FP 3, TN 31, decided FN 1, two unresolved positives and one
unresolved negative. Unresolved negatives are not counted as correct negatives.

- **J20:** `spring` was positive and became unresolved. L6 acknowledged the
  seasonal reading and mattress association, but rejected their interaction.
- **D01:** the earlier negative became unresolved. L6 no longer made the earlier
  close-sense rejection and instead withheld contextual support.
- **D17:** remained a false positive under unchanged gold. The stricter prompt
  still accepted the chain-mail/postal-mail analysis.
- **J13/J17:** stayed positive with different selected targets after continued
  search (`living room` → `room`, `overflowing` → `letter`). Target agreement
  stayed 15/25 overall.

Age algorithms were unchanged. Age-label agreement on original gold puns fell
from 49/75 to 47/75, with assessed labels falling from 69 to 66 because J20 no
longer reached age assessment. This is a detection propagation effect, not an
age-algorithm comparison.

The treatment replay took 94.6 seconds. It replayed 381 unchanged SDK replies and
made 44 new calls. Replay time does not measure fresh full-run latency. The
already inspected 60-item corpus is a regression set here, not unseen data.

## Anonymous review

All 27 changed assignment outputs were reviewed in both A/B orders: **54/54
valid reviews**, with no identity, corpus ID, gold or aggregate score supplied.
The fixed full-assignment rubric was used. This subset includes explanations
that changed despite an unchanged detection, not only changed decisions.

| Both-order preference | Cases |
|---|---:|
| Contextual draft | 8 |
| Baseline | 2 |
| Tie | 6 |
| Preference changed with order | 11 |

Mean humor-explanation rating on these changed outputs increased from 1.72 to
1.85 on the 0–2 rubric. Detection-reasoning rating was 1.81 versus 1.80. These
are ratings on changed outputs from a reviewer in the same model family, not
new aggregate ratings for all 60 items or a human validation.

For J20, both reviewer orders recognized the pun and preferred baseline. For
D17, both recognized wordplay and preferred the draft's explanation, disagreeing
with project gold. D01's preferences changed with order. These disagreements
remain available for human adjudication; they do not authorize automatic gold
changes. The reviewer also continued to flag weak age evidence in both versions.

## What to retain and change next

Retain the new family-separated cases, request-matched replay harness, candidate
histories and anonymous materials. Keep the production prompt at baseline.

The observed responses suggest that the draft's wording about preserving the
candidate's referent can undercredit a legitimate indirectly evoked frame or
intentional misunderstanding. A future development revision should explicitly
separate an **asserted use**, a **conventionally evoked reading**, and an
**unsupported topic association**, preserving the first two when they explain
the text. Each reading should identify its cue and role in the actual lexical
interaction. This should improve evidence inspection before adding a stronger
runtime rejection gate. Do not insert the disputed course items as examples.

Before another adoption decision, independently review the ambiguous controls
and use new confirmation families. Keep current gold, thresholds and this failed
trial intact. Age-source coverage remains a separate improvement task.

## Artifacts and reproduction

- [Frozen design and acceptance criteria](../experiments/contextual_wordplay/protocol.md)
- [New development/confirmation cases](../corpus/prompt_development/contextual_v1/README.md)
- [Experimental L6 template](../experiments/contextual_wordplay/l6_contextual_v1.md)
- [Complete metric and review summary](contextual_wordplay_comparison_20261002.json)
- [Comparison runner](../scripts/compare_contextual_wordplay.py)
- [Summary script](../scripts/summarize_contextual_wordplay.py)

Run: `runs/contextual_wordplay/20261003T034408.133350Z/` (October 2 locally).
It retains all source/resources, inputs and expectations, prompt variants,
requests/responses, candidate findings, changed outputs, hashes and both review
orders. Human packets cover all 60 cases in `blind_review/packets.html`; the LLM
review subset contains all changed outputs. Do not open `identity_key.json`
before human rating. Automated phrase-overlap audits found no matches/hints
against 4,760 known corpus entries; they do not establish absence of paraphrase
or model-training overlap.

To recompute the completed summary without API calls:

```bash
.venv/bin/python \
  runs/contextual_wordplay/20261003T034408.133350Z/postprocessing_summary.py \
  --run runs/contextual_wordplay/20261003T034408.133350Z
```

The summary helper was added after inference; its SHA is recorded separately.
It combines frozen scores, predeclared acceptance checks and raw anonymous
reviews. It does not select outputs, rewrite evidence, retune prompts or invoke
new inference. Production source hashes still match the baseline snapshot.
