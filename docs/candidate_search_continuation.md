# Completing the candidate search

## Diagnosis

The prompt cleanup comparison completed both 60-item arms. All-item binary
accuracy stayed at 31/60; exact-label accuracy changed from 31/60 to 29/60.
Thirteen final labels changed, and twelve of those cases already had different
L4 findings despite identical L4 prompts. These results do not isolate a causal
effect of the L5/L6 template cleanup.

In the cleaned arm, 19 of 22 insufficient-evidence findings came from the search
limit. L3 knew that more than eight lexical terms had been retrieved but had
discarded their candidate entries. L4 assessed eight terms, then correctly
refused a completed negative verdict while untested terms remained. Those
19 items have 39 remaining terms in total (one to four each). This count is an
audit of saved search records, not a prediction of how many extra decisions
will be correct.

## Implementation

- Keep L3's existing scoring formula, order and initial top-k of eight.
- Retain the remainder as `deferred_candidates` instead of discarding it.
- Continue L4 in the same order when no candidate has passed, with a separate
  default budget of 24 distinct candidates. This operational cap allows up to
  three initial-queue lengths and bounds API cost; it is not a calibrated
  decision threshold.
- Save all validated candidate findings and the termination reason in
  `l4_search`, alongside the existing raw attempt records.
- Preserve exact source-quote validation and the single corrective request.
  Persistent validation failure stops the stage. A valid uncertain finding
  stays uncertain even after every retrieved candidate has been examined.
- Do not produce a negative from untested candidates. An explicitly requested
  target-only negative also cannot establish a whole-text negative when other
  retrieved candidates remain unassessed.

No production prompt, gold label, L3 score weight, L5 decision threshold or age
threshold was changed for this repair. Inputs, rather than item IDs or gold
answers, determine the search. Positive candidates found in the first eight
retain the existing stop behavior. Longer searches add API requests and latency
for items that previously stopped at the search limit.

## Evaluation

No new live evaluation score is reported for this implementation. The previous
paired results and their frozen source snapshots remain unchanged.

For a fresh full run of the current corpus:

```bash
PYTHONPATH=src .venv/bin/python -m crack.runner \
  --input corpus/joke_corpus_blind.jsonl \
  --eval corpus/joke_corpus_gold.jsonl \
  --backend openai --concurrency 4 --candidate-budget 24 \
  --output runs/candidate_continuation
```

Use a fresh output and omit `--resume`, so existing decided records are not
reused under a different search budget. A control run can use the same code,
prompts and settings with `--candidate-budget 8`. Repeat both budgets and retain
all runs when assessing end-to-end performance; report all-item accuracy,
decided-item accuracy, coverage, false positives/negatives, failures and search
stop reasons together.

For the narrower question of L5/L6 prompt effects, freeze one shared set of
L1-L4 results and rerun only downstream detection stages under the two prompt
versions. Separate that experiment from the candidate-budget repair. Do not
tune either thresholds or rules against individual current-corpus errors.
Use the fixed development set for rule drafting, then evaluate frozen rules
on an independent held-out corpus before claiming generalization.
