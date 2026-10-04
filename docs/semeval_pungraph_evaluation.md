# SemEval detection and PunGraph interpretation

## Tasks and metrics

| Evaluation | Inputs | Items | Metrics |
|---|---|---:|---|
| CRACK detection evaluation | Text | 2,250 | Binary precision, recall, F1, accuracy, decision coverage |
| CRACK end-to-end interpretation | Text; target found by CRACK | 1,298 official interpretation IDs | Two-sense Acc, PMA, one-to-one Acc, pair coverage |
| CRACK supplied-target interpretation | Text and marked pun word | Same 1,298 IDs | Same local interpretation evaluator |

[PunGraph v1](https://arxiv.org/abs/2609.16557v1), Table 1 and Section 5.3,
evaluates meaning explanations. Acc requires both explanations to match gold;
PMA requires at least one. The pun word is supplied (Section 3.2 and the PDF's
Appendix C). Table 2 gives 1,298 homographic SemEval examples, matching the
official interpretation split's size. This is a different task from detection.

The paper gives 0.50 for retrieval routing, but does not identify its semantic
encoder, Table 1 evaluation threshold or homographic F1 formula. The
[author repository](https://github.com/ysu132/PunGraph), inspected at
`034ed8e9f52962d6b52934a10cd53c7dd8d04595`, contains dataset and graph resources;
it supplies no evaluator or SemEval ID manifest. Evaluator protocol details
are retained in [benchmark_references.json](benchmark_references.json).

CRACK reports its configured local evaluator. The missing author settings
prevent exact reproduction of the paper's interpretation evaluator. CRACK's
interpretation F1 remains null; detection F1 is never substituted for it or
derived from Acc/PMA.

## Declared local protocol

The protocol is `crack-semeval-interpretation-v2`. It uses
`sentence-transformers/all-MiniLM-L6-v2` through FastEmbed, normalized cosine
similarity, and **0.50** as its predeclared primary threshold. The report also
retains every threshold from 0.30 to 0.70 in steps of 0.05. This sensitivity sweep
is diagnostic; select no new primary threshold from the test results.

For each of the two generated explanations, take its largest similarity to any
official acceptable gloss. Acc requires both maxima to reach the threshold;
PMA requires either. Also calculate a stricter one-to-one result: two predictions
must match different gold meaning slots, allowing their order to swap. This
exposes cases where both predictions match the same meaning.

Score only locally accepted L4 PASS responses whose exact quotes and candidate
identifier pass the existing validator. Rejected attempts are retained but never
scored as valid evidence. In the end-to-end view, the final detection must also
be a verified PUN at the official marked word (case and surrounding whitespace
are ignored; no stemming or synonym substitution is used). A missing, failed,
wrong-target or unaccepted pair counts as incorrect in
the full 1,298-item denominator, and its reason is recorded in per-item output.

The supplied-target job performs normal surface analysis, retrieves **all**
dictionary senses for the marked word, and calls the existing L4 prompt and
validator for that candidate. It evaluates interpretation only: it does not
produce detection or age scores, and it does not run L5/L6 joke confirmation.
Its input schema has only ID, text, marked word and word ID. No correct gloss,
sense key, label or answer-bearing demonstration enters inference.

## Official references

The scorer reads the original SemEval archive and joins Subtask 3 word IDs to
Subtask 2 text IDs. Official interpretation answers use **WordNet 3.1** and
semicolon-delimited sets of acceptable sense keys. The new reference builder
keeps both sets and resolves every key in that exact dictionary version.

Preparation found **127** interpretation examples with multiple acceptable keys
in at least one slot; all official keys resolved successfully. The old converted
two-gloss gold could discard these alternatives or substitute unrelated senses.
Its exploratory re-score remains a historical artifact, not a result under v2.
The existing corpus files and labels are preserved; new interpretation
references are written under ignored `data/semeval_benchmark/`.

The archive and WordNet resource checksums are pinned in the evaluator. At run
start, copy the inputs, reference sets, prompts and comparison references into
the run directory. Save source/config hashes, loaded encoder artifact hashes,
package versions, threshold settings, raw L4 attempts, normalized embeddings
and per-item match matrices. Stop if source/config changes between jobs.

Detection recall includes all 1,607 gold positives. Unresolved positive cases
remain in that denominator, and all unresolved cases count against full-set
accuracy; their outcome labels stay separate. The existing `evaluate_run()`
decided-case metrics are retained as additional diagnostics. Reports present
CRACK's metrics without assigning a position among published systems.

## Run

Install the optional evaluator once:

```bash
.venv/bin/python -m pip install -e '.[eval]'
```

Prepare the official resources without LLM calls:

```bash
.venv/bin/python scripts/run_semeval_benchmarks.py --prepare-only
```

Run both experiments and generate the comparison report:

```bash
.venv/bin/python scripts/run_semeval_benchmarks.py \
  --backend openai \
  --concurrency 8 \
  --candidate-budget 24 \
  --output runs/semeval_benchmark
```

This command makes fresh inference calls for 2,250 detection items and a
**separate 1,298-item supplied-target job**. It then scores both interpretation
views offline. Use `--skip-given-target` for detection plus only its end-to-end
interpretation diagnostic. Keep the provider/model settings fixed during a run.

The output directory contains:

- `comparison.md`: readable CRACK detection metrics and interpretation tables.
- `comparison.json`: metrics and machine-readable comparison references.
- `detection_summary.json`: full-set detection metrics, saved before the
  supplied-target job starts.
- `detection/<timestamp>/records.jsonl` and `evaluation.json`.
- `given_target/records.jsonl` and `run_meta.json`, when enabled.
- `interpretation_scores/{end_to_end,given_target}/evaluation.json`.
- `interpretation_scores/{end_to_end,given_target}/per_item.jsonl`: reference
  alternatives, selected explanations, similarity matrices and threshold results.
- `interpretation_scores/{end_to_end,given_target}/per_item.embeddings.npz`.
- `suite_manifest.json`, `inputs/`, and `prompts/`: frozen settings and inputs.

Rebuild a completed suite's reports without LLM calls:

```bash
.venv/bin/python scripts/run_semeval_benchmarks.py \
  --score-only runs/semeval_benchmark/<timestamp>
```

SemEval has no human age-comprehension labels, and CRACK does not implement the
paper's heterographic replacement task. Neither is included in these scores.

## Preparation status

Official resource preparation completed on 2026-10-02: 2,250 detection IDs/texts
and binary labels match the current corpus; 1,298 interpretation records were
generated with all WordNet 3.1 alternatives. No new LLM benchmark calls or test
suite runs were made while preparing this workflow. New CRACK comparison scores
will be produced when the fresh inference command completes.
