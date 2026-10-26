# Exact homophone retrieval and L4 sound-interaction freeze

This is the implementation to rerun after the October 25 engineering fixes.
No new live inference was performed while preparing this change. The next
soundalike and regression runs should be kept as results of this frozen
configuration, including failures and disagreements.

## Local retrieval

Every unique content word queries the pinned official CMUdict reverse index.
A returned spelling must be absent from the current text, have an identical
normalized pronunciation, and have at least one OEWN sense. Function words and
shared inflectional bases are excluded. Primary/secondary stress is ignored
according to the existing pronunciation pipeline, while AH0/ER0 reductions
remain distinct. Words sharing a spelling prefix are not automatically the
same lexeme. No benchmark pair list or gold target is used during retrieval.

Existing hyphen merging and in-text graded similarity retrieval remain.
Candidates sharing a source span are merged, preserving the source of each
alternate. Results use the existing similarity/spatial/alphabetic ordering and
the existing limits: four soundalike candidates, three alternates each, and
four additional L3 soundalike slots. Thresholds remain p95 for both retrieval
and verification. No near-neighbor expansion or threshold reduction was added.
OEWN dictionary access remains serialized for concurrent corpus workers.

The local comparison uses all 79 authored soundalike cases. Thirty-five
positives are eligible for soundalike target recall; the separate compound
resegmentation positive is excluded, as in the existing finder evaluation.

| Local finder metric | Before | After |
|---|---:|---:|
| Annotated alternate supplied | 2/35 (5.7%) | 22/35 (62.9%) |
| Annotated pun expression flagged | 4/35 (11.4%) | 27/35 (77.1%) |
| Negative texts yielding any candidates | 9/43 (20.9%) | 38/43 (88.4%) |

These are retrieval measurements, not LLM detection scores. Ordinary texts
often contain words with homophones. Additional exact candidates can also
displace earlier near-pair candidates under the unchanged cap. Neither the
retrieval gains nor the larger negative candidate count establishes final
precision or accuracy. The runtime finder does not read the reference labels;
only the offline comparison script reads them for measurement.

## L4 instructions

Only the `Soundalike assessment` section changed. It now requires an observable
reinterpretation or contrast for a sound pair; co-occurrence, similar sound and
different meanings alone are insufficient. It also requires selecting the
shortlisted expression carrying the sound-based wordplay, rather than
attributing it to another candidate. No corpus joke demonstrations were added.

The full L4 template is saved both
[before](evaluations/exact_homophone_l4_20261025/before/prompts/l4_anchoring.md)
and [after](evaluations/exact_homophone_l4_20261025/after/prompts/l4_anchoring.md).
All final prompt templates, relevant source files and config source are
snapshotted under `after/`, with checksums in `snapshot_manifest.json`.
L5 and L6 templates match the preceding real run byte for byte. Model choices,
candidate budgets, L5 thresholds, lexical resources and calibration are unchanged
from the resource/engineering refresh.

Each actual L4 request is additionally saved in the original run's
`records.jsonl`, at `l4_attempts[].prompt_text`, alongside `prompt_sha256`.
That is the fully rendered instruction plus current text, candidates and
dictionary proposals, not just the template or a version name. Keep these raw
run directories: the existing compact publication script deliberately omits
`l4_attempts` and therefore does not preserve the rendered prompts by itself.

## Reproduction and rerun

The local before/after output and per-item candidate lists are in
`docs/evaluations/exact_homophone_l4_20261025/`. Reproduce retrieval arithmetic
and current candidates without an API call:

```bash
.venv/bin/python scripts/compare_exact_homophone_finder.py --before docs/evaluations/exact_homophone_l4_20261025/finder_before.json --output docs/evaluations/exact_homophone_l4_20261025
```

Use fresh output roots for the two real runs; do not resume records from the
previous source/prompt fingerprint:

```bash
.venv/bin/python -m crack.runner --input corpus/soundalike_blind.jsonl --eval corpus/soundalike_gold.jsonl --output runs/final_soundalike --backend openai --concurrency 8 --candidate-budget 8
.venv/bin/python -m crack.runner --input corpus/joke_corpus_blind.jsonl --eval corpus/joke_corpus_gold.jsonl --output runs/final_regression --backend openai --concurrency 8 --candidate-budget 8
```

The next end-to-end comparison combines the retrieval and L4 instruction
changes; it cannot separately estimate their contributions to detection
accuracy. Only the local retrieval comparison isolates the retrieval effect.
Preserve all outcomes rather than revising prompts after seeing the final run.

Verification before the rerun: **588 offline tests passed**, with 10 live tests
deselected and two existing FastAPI lifecycle deprecation warnings. The expanded
prompt overlap audit reports zero failures and zero review hints. Captured
request tests verify that full L4 prompt text and its SHA-256 agree, while
dictionary example sentences remain absent from the request.
