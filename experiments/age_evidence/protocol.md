# Age evidence comparison, frozen before inference

Question: does replacing heuristic L7/L8 with source-linked contextual assessment
improve age reasoning while preserving the detection decision?

## Fixed control and treatment

Control is the completed continuation run at
`runs/candidate_continuation_comparison/20261003T032128.960031Z/continuation/records.jsonl`.
Its source/config snapshot is copied before production edits. Treatment reuses
all 60 original inputs and the identical L1–L6 outputs, candidate ledger, target,
readings and humor explanations. Only L7/L8 are freshly run, for all 26 items the
frozen detector classified as PUN. Non-puns receive no fabricated age verdicts.
Both use the same frozen Kuperman CSV. Model: gpt-6-luna; age stages OpenAI;
8192 completion tokens each; one corrective retry for rejected format/evidence;
four concurrent item workers. No gold access on the inference code path.

No gold, detection threshold, candidate budget or detection prompt changes.
Treatment prompts use abstract rules, no corpus sentences or answer examples.
No parameter tuning or best-run selection after this evaluation. Detection is
asserted identical per item, not described as a new detection benchmark.

## Outcomes

Primary: valid vocabulary citation coverage on the 75 age labels for 25 gold
puns; successful age-call coverage; preservation of unknowns; anonymous review
of age evidence and appropriateness reasoning. Secondary: agreement with fixed
project age labels (not measured child understanding), added API tokens/calls
and elapsed time. Count missing and UNKNOWN/AOA_UNKNOWN as unassessed.
AoA citations concern whole words, not proven sense acquisition. Contextual
sense/wordplay/background judgments remain explicitly labelled model estimates.

Review all 26 detector-positive items, including its false positives, selected
before treatment inference. A/B positions randomized with fixed seed 20261002;
each item reviewed in both orders by gpt-6-luna using the existing fixed rubric.
Reviewer sees original text, ages, shared table and anonymous common-format
outputs, without gold or system identities. Order disagreement is reported;
no reviewer score is used to retune. This is same-family LLM review; retain
anonymous HTML and empty human rating CSV for manual review. Do not credit
well-written reasoning as measured improvement in child comprehension accuracy.

Baseline age stages made no external calls. Compare incremental age costs;
previous detection calls are reused and excluded from added API totals.

## Mechanical schema clarification before the final pass

The first pass is retained at `runs/age_evidence/20261003T182412.372664Z`.
It exposed a response-format ambiguity: L8 sometimes returned objects where
`per_age_reasons` and `inference_issues` require strings, even after correction.
The final pass adds explicit type statements and an abstract JSON shape to the
L8 prompt. It makes no changes to the semantic rules, citations, age derivation,
model, gold or detection. It reruns all 26 positive items, including both
previously accepted and rejected replies, rather than selecting successful
retries. Both complete runs and all raw failures are retained. The final pass
is the one with this explicit schema; it is not selected by its age-label score.

## Missing-value propagation repair

The explicit-schema run is retained at `runs/age_evidence/20261003T184336.938131Z`,
including its anonymous review. Its audit exposed an invalid general assumption
in the new code: a missing AoA value for any selected word forced the entire
vocabulary judgment to UNKNOWN at every age. This conflates missing word-level
measurement with inability to estimate contextual understanding, and particularly
affects grammatical forms outside the rating resource's scope.

The final implementation removes that automatic propagation, preserving every
null citation. L7 must distinguish a contextual familiarity estimate from a
measured rating and explain missing support; genuinely inadequate prerequisites
still permit UNKNOWN. Citation, quote and type checks remain strict. No age
threshold, gold label, item-specific answer or numeric fallback is added.
All 26 items are rerun once under this repaired contract and reviewed in both
orders. Earlier passes remain documented, not deleted or selected by agreement.
Because the corpus audit informed this general repair, these results are
development evidence; an untouched age set is required for a generalization claim.
