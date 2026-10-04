# Candidate continuation: implementation and comparison

## Change

Automatic search now completes L4–L6 for a candidate before accepting it as
the target. A valid semantic rejection or uncertain finding leads to the next
retrieved candidate. Search order, prompts, response contract version 4,
thresholds, scope rules and age algorithms are unchanged. The original budget
of 24 distinct L4 candidates is shared across the whole item. API failures and
persistent evidence-validation failures stop the item.

`candidate_assessments` preserves all candidate findings and typed downstream
outputs. Earlier uncertainty remains visible after later negatives. If every
retrieved candidate has a conclusive rejection, the item can be negative;
remaining/unavailable candidates or unresolved findings require review. A
different candidate can establish a positive only by passing all existing
checks. Age layers use that final target. The same implementation serves the
CLI and web requests. Search version 2 prevents resume from silently reusing
records from the earlier search policy.

## Fixed-prefix result on the current 60 items

Both policies replayed the original **398 SDK replies**, requiring identical
model, messages, response format, temperature when present, output budget and
stage for every request. The control reproduced all 60 original decisions,
targets, meanings and age outputs. Only the continuation policy made new calls
after consuming a text's complete original prefix. One completed pass; gold
was used by scoring after inference.

| Metric | Previous search | Candidate continuation |
|---|---:|---:|
| Binary accuracy, all texts | 55/60 (91.67%) | 55/60 (91.67%) |
| Precision | 92.00% | 88.46% |
| Recall, all 25 gold puns | 92.00% | 92.00% |
| F1, full gold | 92.00% | 90.20% |
| Decision coverage | 58/60 (96.67%) | 59/60 (98.33%) |
| Original + rewrite both correct | 21/25 | 21/25 |
| Exact normalized target matches, all gold puns | 15/25 | 15/25 |
| Additional SDK calls in the completed comparison | 0 | 11 |
| Additional input + output tokens | 0 | 19,653 |
| Common output-contract failures | 0 | 0 |

TP/TN stayed at 23/32. FP increased from 2 to 3; one gold-positive remained a
decided false negative, another remained unresolved. The unresolved negative
became an additional false positive. Age-label matches on the 25 gold puns
remain 49/75, with 69/75 assessed. No age-algorithm change is evaluated here.

The completed continuation replay took 37.5 seconds, most of which concerns
additional model requests. This is **not fresh end-to-end runtime**: the original
requests were served from saved replies, so it cannot establish a speed benefit.
Usage above covers the completed scored trial, excluding an interrupted setup
trial described below.

## What changed per text

- **D09:** L5 rejected `baseball`; the new search examined the seven remaining
  terms and rejected them. The final negative stayed the same, with complete
  candidate accounting.
- **J24:** after L5 could not assess the question-only `stories` candidate, the
  remaining `many` candidate was rejected. The original uncertainty remained
  visible; it was not converted to a negative.
- **D01:** all seven candidates had already been examined before L6 rejected
  `muscles`; the negative stayed the same with no added requests.
- **D17:** after `postal` remained unresolved, search found `mail`. The model
  anchored chain-mail armor in “metal mail carrier sack” and postal letters in
  “postal worker collected eighty paper letters”. Existing L5/L6 checks accepted
  this pair. D17's unchanged gold is negative, so this is a false positive in the
  reported metrics. Whether the rewrite still accidentally evokes wordplay or
  the explanation is strained requires independent human adjudication. The
  model's approval does not resolve that question.

This implementation repairs search completeness; **this corpus comparison shows
no accuracy or pair-success gain and a lower F1**. Additional candidate searches
create more opportunities for a weak interpretation to pass existing semantic
checks. The result supports investigating contextual candidate quality and
whether the selected contrast explains the joke. No rule or threshold was
retuned using D17, and its gold was not changed. This 60-item experiment does
not measure recovery of the previously identified SemEval candidates.

## Audit and review

The initial experiment helper failed to apply per-arm settings, so the control
used continuation instead of the declared old policy. Exact-output comparison
detected the mismatch. That trial was interrupted and excluded in full; its
records are preserved at `runs/candidate_continuation_comparison/20261003T031912.949563Z/`.
The generic helper repair applies the declared settings. The completed trial
replayed and verified the control before running continuation. No earlier
partial outputs were selected for the final score. Calls started in the
interrupted trial may have incurred additional usage outside the table above.

The completed run is
`runs/candidate_continuation_comparison/20261003T032128.960031Z/`.
It preserves source/resources, input hashes, original and new raw responses,
per-candidate histories, changed outputs and anonymous A/B packets with an empty
human-review CSV. The current experiment has not received a new LLM or human
blind review; its inference and program-check results are reported here.

- [Full metric and configuration summary](candidate_continuation_comparison_20261002.json)
- [Fixed-prefix protocol](../experiments/full_assignment/candidate_continuation_protocol.md)
- [Comparison runner](../scripts/compare_candidate_continuation.py)
- [Candidate-search implementation](../src/crack/candidate_search.py)

For a fresh current-corpus run using the new policy:

```bash
PYTHONPATH=src .venv/bin/python -m crack.runner \
  --blind corpus/joke_corpus_blind.jsonl \
  --eval corpus/joke_corpus_gold.jsonl \
  --backend openai --concurrency 8 --candidate-budget 24 \
  --output runs/corpus_candidate_continuation
```

Use `--no-candidate-continuation` for the previous policy. A fresh run samples
all initial model findings again, so it answers a different repeatability/runtime
question from the fixed-prefix intervention above. These project-corpus results
do not replace the saved SemEval benchmark results.
