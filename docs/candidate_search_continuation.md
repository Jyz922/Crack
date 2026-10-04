> Historical experiment. Current search policy `3` checks only the original
> L4 shortlist (up to eight terms), stops on unknown/error, and never resumes
> after L5/L6 rejection. The continuation policy below is retired. Reproduce
> its saved comparisons with frozen source snapshots, not the current runtime.
> See [current response rules](response_validation.md).

# Completing the candidate search

## Extension: candidate-level L4–L6 continuation

Search policy version `2` completes the L5/L6 checks for a candidate before
accepting it as the text's target. If those checks reject it or remain uncertain,
automatic search resumes in the original ranked order, skipping terms already
assessed. The default budget remains 24 distinct L4 candidates for the entire
item. Scope rules, response checks, prompts, semantic thresholds and age
algorithms remain unchanged.

`candidate_assessments` preserves per-term L4/L5/L6 outputs and outcomes. An
uncertain candidate cannot be erased by later negative findings. A complete
negative requires all retrieved candidates to have conclusive rejections;
budget exhaustion or unavailable candidates remain insufficient evidence.
Execution/validation failures stop the item, and are never bypassed by trying
another term. Age assessment runs on the final accepted candidate only.

Use `--no-candidate-continuation` for the previous search policy. Resume checks
the separate search-policy version so older results are not silently reused.
The implementation below describes the earlier L4-only continuation; its saved
results and rationale remain historical records.

The fixed-prefix comparison protocol is in
[candidate_continuation_protocol.md](../experiments/full_assignment/candidate_continuation_protocol.md).
It reuses byte-identical, request-matched SDK replies from the saved 60-item
full-assignment run and calls the model only for new candidates. Both policies
must reproduce that original prefix. This isolates continuation from resampling
the initial findings, and supplies full outputs for anonymous review; it does
not measure fresh end-to-end runtime or generalization.

```bash
.venv/bin/python scripts/compare_candidate_continuation.py --concurrency 8
```

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
