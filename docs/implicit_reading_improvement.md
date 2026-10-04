# Contextually evoked readings in L4

Historical experiment on contract version 4. Its source and scores predate the
current single-request shortlist policy and compact shared age estimates.
See [the October 4 comparison](corpus_recovery_20261004.md) for the current design.

## Baseline and diagnosis

The complete version-4 run at `runs/corpus_v4/20261002T170920Z/` used commit
`d8f2e7fa271d111bb5b3cfdb472071c8f1f25116`, OpenAI `gpt-6-luna`, eight concurrent
workers and a candidate budget of 24. It recorded all 60 inputs with no execution
failures: 49/60 exact-label accuracy, 52/60 binary accuracy and 59/60 decision
coverage. On decided items, TP=19, FP=2, TN=33 and FN=5; one positive item was
unresolved. These are baseline observations, not results for the changed prompt.

Each of the five false negatives had its annotated target assessed at L4. The
saved explanations rejected an alternative because the text did not state a
second event occurred, or because its contextual trigger was treated as topic
association. This supports reviewing L4's interpretation policy; it does not
establish that every proposed alternative or every corpus annotation is correct.

The fixed development set already distinguishes contextual activation from
literal truth. DEV01, DEV03 and DEV07 intend a second semantic frame to be evoked
by wording around a candidate whose primary reference is otherwise selected.
Their paired controls supply only the primary frame. These development cases
justify checking the distinction without copying evaluation sentences into the
production prompt. The development texts, labels and hashes remain frozen.

## Change

Only `prompts/l4_anchoring.md` changes production inference:

- A meaning can be directly used or indirectly evoked by a conventional semantic
  link in the text. Both meanings need not be simultaneous factual events.
- For a positive finding, identify exact source cues, link each cue to its
  reading, and explain the interaction that creates the lexical expectation,
  double-take or shift. A dictionary alternative or incidental topic alone is
  insufficient.
- Do not invent events, participants or missing replies. A selected literal
  reference can coexist with an evoked frame, but explicit disambiguation does
  not create wordplay by itself.
- Before a candidate-level negative, consider the strongest plausible alternate
  reading and explain its rejection within the existing `reasoning` field.

No new response fields, stages, retries or score thresholds are added. Source
quotes remain exact; invalid responses still require a corrective reply rather
than local evidence repair. L5/L6 continue to assess any newly accepted L4
finding. Response contract version 4 is unchanged because its executable checks
and schema are unchanged; the prompt SHA-256 distinguishes this revision.

The L4 template changes from 4,760 to 4,866 characters and from 663 to 667
whitespace-separated words. These are text lengths, not measured token counts
or latency. The candidate call schedule is unchanged; admitting more candidates
to downstream stages can still change total calls and elapsed time.

The existing comparison-test fixture was also brought into agreement with the
contract-version field already required by the comparison harness. No new test
cases were added and no tests were run for this change.

## Safeguards and saved artifacts

The following remain unchanged: corpus texts and gold labels, fixed development
examples, ranking weights, candidate budget, source-quote validation, L5/L6
templates and thresholds, final decision rules and provider configuration.
No item IDs, evaluation targets, evaluation sentences or word/meaning answer
pairs were added to production instructions.

The current 60-item corpus has been inspected during development. Treat a new
run on it as a regression observation; it cannot establish performance on unseen
data. Audit uncertain minimal-pair annotations separately and preserve current
gold for the comparison rather than changing labels to match model outputs.

Local snapshots are retained at:

- `runs/implicit_activation/20261002T193612Z/before_prompts/`
- `runs/implicit_activation/20261002T193612Z/after_prompts/`
- `runs/implicit_activation/20261002T193612Z/before_manifest.json`
- `runs/implicit_activation/20261002T193612Z/after_manifest.json`
- `runs/implicit_activation/20261002T193612Z/overlap_audit.json`

The before snapshot matches the source hashes of the completed baseline run.
The static phrase-overlap audit reports zero failures and zero review hints
across 4,760 evaluation-reference rows and 18 prompt/development subjects.
This checks text overlap, not unseen-data performance or semantic correctness.
No new API calls or accuracy result are reported here. OpenAI's
[prompt engineering guidance](https://developers.openai.com/api/docs/guides/prompt-engineering)
notes that model outputs can vary and recommends evaluating prompt changes.

## Fresh inference

Inspect the fixed development set first, then use a fresh regression run. Omit
`--resume`: contract-compatible old predictions were made under different
semantic instructions and must not stand in for new inference.

```bash
PYTHONPATH=src .venv/bin/python -m crack.runner \
  --input corpus/prompt_development/v1/blind.jsonl \
  --eval corpus/prompt_development/v1/expected.jsonl \
  --backend openai --concurrency 4 \
  --output runs/implicit_activation_development

PYTHONPATH=src .venv/bin/python -m crack.runner \
  --input corpus/joke_corpus_blind.jsonl \
  --eval corpus/joke_corpus_gold.jsonl \
  --backend openai --concurrency 8 --candidate-budget 24 \
  --output runs/corpus_implicit_activation
```

For a controlled comparison, the existing harness can run both frozen prompt
directories under identical current pipeline code:

```bash
.venv/bin/python scripts/compare_prompt_versions.py \
  --before-prompts runs/implicit_activation/20261002T193612Z/before_prompts \
  --after-prompts runs/implicit_activation/20261002T193612Z/after_prompts \
  --backend openai --concurrency 8 --repeats 3 \
  --output runs/implicit_activation_comparison
```

These commands make API requests; they have not been executed for this revision.
Keep all repeated runs and report false positives, false negatives, uncertainty,
failures and coverage with accuracy. Inspect the frozen rules on an independent
corpus before claiming generalization or deciding to keep the change based only
on the highest observed regression score.
