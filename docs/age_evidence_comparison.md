# L7/L8 age evidence comparison — 3 October 2026

## What changed

L7 now considers required vocabulary throughout the sentence, both meanings,
wordplay and background knowledge. It copies checked word-level AoA citations
from the frozen Kuperman table, records contextual estimates and prerequisites
for every requested age, and leaves sense acquisition ages unmeasured. Default
ages, secondary-sense offsets, easiest-gloss-word estimates and genre-specific
age floors are no longer used.

L8 separately assesses content and inference, records age-specific reasons and
quoted concerns, and combines its axes with L7 in code. Missing information and
failed calls remain unknown. The UI displays real citations/reasons and no longer
inserts a default acquisition age, recommended age or unassessed safety pass.

See [age evidence](age_evidence.md) for the contract and the primary AoA source.

## Fixed comparison

The 60 texts, target ages, gold and detector outputs are unchanged. All L1–L6
results, candidate ledgers, selected targets/readings and detection decisions
are asserted identical. Only age stages rerun for the 26 detector-positive
outputs, including its three false positives. This is an age-only comparison,
not a fresh detection or SemEval run. The frozen detector still has 55/60 binary
correct decisions (91.67%), F1 90.20%, and coverage 59/60 (98.33%).

### Age labels on the 25 gold puns

| Metric | Old age stages | Final age stages |
|---|---:|---:|
| Match to all 75 project age labels | 49/75 (65.33%) | 37/75 (49.33%) |
| Judgment coverage | 69/75 (92.00%) | 45/75 (60.00%) |
| Match among assessed labels | 49/69 (71.01%) | 37/45 (82.22%) |
| Age entries with at least one checked rated-word citation | 0/75 | 69/75 (92.00%) |
| Completed age-stage pairs, all detector-positive texts | 26/26 | 26/26 |
| Age-stage errors | 0 | 0 |

The assessed-label improvement uses a smaller set of judgments, so it does not
establish improved overall age accuracy. Of the 30 unassessed gold-pun age labels,
24 have explicit uncertainty in L7 and six belong to two undetected gold puns.
Project age labels measure agreement with project annotations, not observations
of children understanding the jokes. Citation coverage measures recorded support
for vocabulary ratings; it does not prove the model's sense or developmental
judgments. The old stages used the local table but did not emit individual
checkable citations in the common comparison output.

### Time and calls

The final pass made 52 age API calls using gpt-6-luna and 189,965 tokens. Mean added
age time was 35.95 seconds per detector-positive item with three requested ages;
the four-worker age-only batch took 252.2 seconds. Old local heuristic stages
averaged about 0.062 seconds. Web requests evaluate more ages and can take longer.
Detection calls were reused and excluded from these added costs. Anonymous
review is an additional experiment cost, not part of production inference.

## Development repairs and retained earlier results

The first pass (`20261003T182412.372664Z`) had five L8 failures from ambiguous
string/object output types. Fields were clarified with an abstract JSON shape,
without corpus answers, and all 26 texts rerun.

The explicit-schema pass (`20261003T184336.938131Z`) completed all 26 pairs, but
its missing-value rule forced overall vocabulary UNKNOWN whenever any required
word lacked an AoA rating. This affected grammatical forms outside the resource's
coverage. That general assumption was removed: missing numeric measurements
remain null; contextual familiarity estimates are permitted when justified,
and inadequate prerequisites still produce UNKNOWN. No numeric fallback,
item-specific answer, gold change or threshold tuning was introduced.

| Retained pass | Age label matches / 75 | Assessed / 75 | Age-stage errors |
|---|---:|---:|---:|
| Initial contract | 27 | 34 | 5 |
| Explicit field types | 25 | 28 | 0 |
| Final missing-value handling | 37 | 45 | 0 |

These general repairs were informed by the corpus audit. The final pass is
selected for corrected contracts, not by choosing the highest agreement. These
are development results; an untouched age set and human review are needed before
claiming improved age generalization. All source snapshots, raw responses,
rejected attempts, input hashes and earlier passes remain saved.

## Anonymous review

The fixed rubric reviewed all 26 detector-positive outputs in both A/B orders,
with system identities and gold hidden. All 52 reviews completed, and all 26
cases preferred the final age-evidence version in both orders (no order flips).

| Reviewer dimension, 0–2 | Old age stages | Final age stages |
|---|---:|---:|
| Age evidence | 0.00 | 1.96 |
| Appropriateness reasoning | 0.10 | 1.98 |

Each mean includes both review orders, so these are 52 correlated ratings of 26
texts, not 52 independent examples. The reviewer was gpt-6-luna, the same model
family as the analysis stages. This supports improved explanation and recorded
basis, not improved measured child understanding. Small reviewer differences
on unchanged detection/meaning outputs illustrate scorer variation and possible
influence from the surrounding age answer; they do not count as detection gains.

Manual ratings remain pending. Anonymous `packets.html`, `human_ratings.csv` and
the fixed rubric are saved under the final run's `blind_review/` directory. The
identity key is a separate file; reviewers should not open it before scoring.
The 24 explicitly uncertain age judgments are also collected separately for
review, without changing gold.

## Current decision

The source-linked age contract and UI are implemented. They improve traceability
and the reviewed explanations, but overall project age-label agreement remains
lower and adds about 36 seconds per positive text. Neither matching labels only
among assessed cases nor the LLM preference establishes improved overall age
accuracy. The next evaluation should use human review and a newly collected,
untouched age set, with sources for sense familiarity and background knowledge.
The current corpus and gold stay fixed. A subsequent
[offline aggregation correction](age_aggregation_comparison.md) preserves
estimated barriers that were hidden by other unknown dimensions; the results
above and their anonymous reviews retain the original aggregation.

See [machine-readable summary](age_evidence_comparison_20261003.json).

## Implementation checks

Python source parsing/imports, frontend JavaScript syntax and `git diff --check`
completed. All 60 historical native records remain readable. The final evaluated
package matches the production source and prompts at the time of that run. Detection modules and
prompts match the saved prechange baseline byte for byte. The full unit test suite
was not run for this request. Changes remain local and uncommitted.
