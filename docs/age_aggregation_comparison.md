# Age aggregation comparison — 3 October 2026

## Rule and implementation

The old L7 aggregation returned `AOA_UNKNOWN` whenever any prerequisite was
unknown, even if another prerequisite had an explicit `UNLIKELY` judgment.
The revised rule reports the existing estimated barrier while retaining every
unknown dimension. Uncertainty alone cannot establish a barrier, and a
`FULLY_COMPREHENSIBLE` result still requires all five dimensions to be `LIKELY`.

Each age has a program-derived summary containing `status`,
`barrier_dimensions`, `unknown_dimensions` and `fully_assessed`. The UI lists
barriers and unknown prerequisites separately. A barrier is a contextual model
estimate, not an observation of a child failing to understand the text.

L8 uses the named dimensions to distinguish vocabulary/meaning difficulty from
wordplay/background difficulty when combining otherwise positive content and
inference axes. It retains independent negative content/inference findings and
null axes. No unknown prerequisite becomes a pass. Model instructions, response
fields and exact citation/quotation checks are unchanged. Aggregation version
`2` is recorded separately from age response contract version `1`; resumed runs
must match both.

## Frozen offline comparison

The source is the completed age-evidence run
`runs/age_evidence/20261003T185243.323665Z/`. All 60 saved records are included.
The accepted raw replies for all 26 completed L7/L8 pairs were revalidated
against the frozen input table and existing field/source contracts. Only the
program-derived summaries and combined age labels were recomputed.

Preservation checks require identical text, ages, raw attempts, vocabulary
citations, five-dimensional findings, reasons, L8 axes, traces, L1–L6 results,
candidate ledgers and detection outputs. The current AoA CSV must have the same
hash as the saved resource. Gold is read only after recomputation for scoring.
There were **zero new API calls and zero new API tokens**.

### Age labels on the 25 gold puns

| Metric | Previous aggregation | Revised aggregation |
|---|---:|---:|
| Agreement with all 75 project labels | 37/75 (49.33%) | 42/75 (56.00%) |
| Summary-label decision coverage | 45/75 (60.00%) | 53/75 (70.67%) |
| Agreement among decided labels | 37/45 (82.22%) | 42/53 (79.25%) |
| All five dimensions assessed | 45/75 (60.00%) | 45/75 (60.00%) |
| Age entries with unknown dimensions | 24 | 24 |
| Both estimated barriers and unknown dimensions | 8 | 8 |
| Age entries without an assessment because detection missed the pun | 6 | 6 |
| Age entries with at least one checked rated-word citation | 69/75 (92.00%) | 69/75 (92.00%) |

The extra eight summary decisions expose existing barriers; no missing evidence
was supplied. Complete dimension coverage remains 60%. The assessed-label
agreement decreases because the newly included decisions match five of eight
project labels. Project agreement measures correspondence with the corpus
annotations, not measured child comprehension.

On all 180 corpus age labels, agreement changes from 41/180 to 46/180 and
summary-label coverage from 50/180 to 59/180. Controls do not receive invented
age assessments; the 75 gold-pun labels are the primary age comparison.

### Changed labels

Nine comprehension labels change from `AOA_UNKNOWN` to
`PARTIALLY_COMPREHENSIBLE`: eight gold-pun age entries and one detector false
positive. Only one combined appropriateness label changes.

| Item | Age | Estimated barrier dimensions | Remaining unknown dimensions | Appropriateness change |
|---|---:|---|---|---|
| J01 | 6 | vocabulary, wordplay | sense A, sense B | none |
| J04 | 8 | vocabulary, sense B, wordplay, background | sense A | none |
| J09 | 6 | vocabulary, wordplay | background | none |
| J07 | 6 | sense A, wordplay | vocabulary | none |
| J19 | 8 | vocabulary, wordplay | sense B, background | none |
| J16 | 6 | vocabulary | wordplay | none; still `UNKNOWN` |
| J25 | 8 | vocabulary, sense A, wordplay | sense B | `UNKNOWN` → `VOCABULARY_TOO_ADVANCED` |
| D03 | 6 | vocabulary, wordplay | sense A, sense B | none; detector false positive retained |
| J20 | 6 | vocabulary, wordplay | sense B, background | none |

Item IDs appear only in the change ledger and this report. The production rule
contains no corpus IDs, answers, gold-dependent exceptions or tuned thresholds.

### Detection and timing

The saved detector remains **55/60 binary correct (91.67%)**, **90.20% F1**
using the full gold-positive denominator, and **59/60 decision coverage
(98.33%)**. The precision, recall, classification outputs and explanations are
identical. This is not a fresh detection or SemEval evaluation.

Offline processing took approximately 0.05 seconds after imports; this is not
LLM inference latency. Original inference durations remain in the source and
derived records. The prior age-stage mean of 35.95 seconds is unchanged.

## What remains to evaluate

The L8 axes and reasons were generated using the previous L7 summary. This
comparison isolates the program's combination rule; future L8 calls receive
the revised L7 summaries and may return different estimates. The existing
anonymous LLM ratings belong to the previous age outputs and were not reused
as ratings of this revision. No new blind review or human review was performed.

The 24 age entries with unknown dimensions still need additional evidence or
review. Human assessment and an untouched corpus are needed to evaluate age
generalization. Current texts, gold and detection thresholds remain fixed.

## Artifacts and reproduction

The offline run is `runs/age_aggregation/20261003T201305.305628Z/`:

- `manifest.json`: source/input hashes, fixed rule, evaluator and source snapshots.
- `source_records.jsonl`: unchanged saved inference outputs and SDK observations.
- `reaggregated/records.jsonl`: derived outputs with original inference durations.
- `changes.json`: every changed age label, barrier and unknown dimension.
- `summary.json`: metrics for both aggregations and preservation checks.
- `before/src/crack/` and `workspace/`: previous and revised source snapshots;
  `workspace/data/aoa_kuperman.csv` retains the rated-word resource.

Recompute using the frozen script and local artifacts:

```bash
.venv/bin/python runs/age_aggregation/20261003T201305.305628Z/reaggregate_age_results.py \
  --run runs/age_aggregation/20261003T201305.305628Z
```

The script rejects modified inputs, source, evaluator or resources and disables
model-call entry points. See the
[machine-readable summary](age_aggregation_comparison_20261003.json).

## Implementation checks

All production Python files and the offline runner parsed successfully, the
updated modules imported, frontend JavaScript syntax passed, and `git diff
--check` was clean. All 60 derived records were adapted through the actual
frontend payload builder: 78 age summaries retained their dimensions, including
nine summaries with both barriers and unknowns (one is a detector false positive).
The previous snapshot and evaluated current source matched the saved hashes.
No unit-test suite, live pipeline inference or new reviewer calls were run.
Changes remain local and uncommitted.
