# Response validation and unresolved decisions

The detection pipeline uses response contract version `4`. Each LLM request
contains the current text and the complete stage prompt. L4, L5, and L6 responses
are checked locally before their findings can affect the final decision.

## Enforced checks

- **L4:** all response fields are required; status values must match the schema;
  `target_term` must match the supplied candidate's spelling, allowing only
  letter case and surrounding whitespace differences. The accepted result uses
  the supplied identifier; the logged raw/parsed response is preserved.
  Lemmatization, internal whitespace changes and spelling substitutions are
  rejected. This identifier rule does not normalize source quotes.
  A resegmentation pass must
  name a supplied `split_options` pair in `split_parts`; other findings use an
  empty array. Alternative split proposals survive L3 term deduplication.
  Every nonempty quote must occur verbatim in the input. A pass requires two
  nonempty, different meaning descriptions and explicit context evidence,
  relation, and resolving sense. Non-split anchors must be different context
  spans, not just the candidate word. Same-word anchors are allowed only for a
  detected compound-split candidate. A negative `ONE_SENSE_ONLY` finding still
  requires a described reading and a source quote.
- **L5:** every subscore and the `evidence_sufficient` flag are required. Scores
  must be finite JSON numbers in [0, 1]. If evidence is insufficient, all scores
  must be null and the explanation must identify the missing information.
- **L6:** paraphrases, both boolean findings, status, ablation result, and
  explanation are required. A distinctness claim must agree with its boolean
  findings and use different paraphrases. Unknown findings use null flags and
  `SKIPPED` ablation. Compound-split candidates also receive this assessment.
- **Final decision:** a positive result requires L4 PASS, L5 RESOLUTION_PASS,
  and a completed L6 SENSES_DISTINCT finding with SUPPORTED ablation. Missing or
  skipped L6 findings cannot produce a positive decision. L6's ablation remains
  a model assessment; it is not a separate run of a rewritten text. It concerns
  disappearance of the claimed two-meaning wordplay, not disappearance of every
  other source of humor. The explanation identifies the replacement and contrast.

L4 permits one corrective request after a JSON or contract rejection, for the
same candidate. Each attempt saves the raw response, parsed object when
available, prompt SHA-256, acceptance flag and rejection reason in
`l4_attempts`. The corrective request includes the local validation error;
quotes are never silently aligned or normalized. A valid negative or unknown
finding is accepted without a correction. Transient provider retries remain
separate from this single contract correction.

Persistent malformed responses, missing fields, contradictory findings,
reported output truncation/refusal, and request failures produce an execution
failure. They are not converted into negative examples or filled in with
passing defaults.
Dependent stages stop after a detection failure or unresolved prerequisite.

These checks establish response completeness and checkable consistency. Whether
a quote really supports a proposed meaning remains a semantic judgment to
evaluate against annotated examples. Echoing the correct `target_term` does not
prove that both meaning descriptions actually concern that word.

L3 retains the ranked tail in `deferred_candidates` after its initial top-k
queue (default eight). L4 examines successive candidates until it finds a pass
or exhausts its separate `L4_MAX_CANDIDATES` budget (default 24). Remaining terms
are promoted into the active list as they are examined, preserving their split
proposals and the selected target for L5/L6. `l4_search` saves each validated
candidate finding, the remaining count and the stop reason. Persistent invalid
evidence aborts the stage; another candidate cannot conceal that failure.

A candidate-level `ONE_SENSE_ONLY` result becomes a text-level negative only
when all supplied lexical candidate terms were assessed. Budget exhaustion,
unavailable candidate data, unresolved findings or no retrieved candidates
remain `INSUFFICIENT_EVIDENCE`. Completeness here concerns retrieved lexical
proposals; it does not establish that a dictionary covers every possible
mechanism. The CLI's `--candidate-budget` changes only the search budget.
See [candidate search continuation](candidate_search_continuation.md).

## Result states

`final.detection_status` and the web response distinguish:

| State | Meaning | Next action |
|---|---|---|
| `PUN` | All required positive detection checks completed | View the analysis |
| `NON_PUN` | A completed check rejected the proposed wordplay | View the finding |
| `INSUFFICIENT_EVIDENCE` | Required context or an assessment is missing | Review or add context |
| `EXECUTION_FAILED` | A request or response validation failed | Inspect the trace and retry |
| `OUT_OF_SCOPE` | A different mechanism needs assessment | Review separately |

The last three states set `review_required: true` and carry a `review_reason`.
They do not show a confirmed joke, a negative judgment, invented senses, or a
default confidence/safety pass. The existing detailed `main_classification`
labels are retained. The UI's resolution score is a stage score, not a
calibrated probability of correctness.

## Evaluation denominators

Evaluation covers every ID in the supplied gold file. Missing predictions count
as execution failures; duplicate or unknown prediction IDs are rejected.

- `decision_coverage` = decided items / all gold items.
- `classification_accuracy` = correct exact-label decisions / all gold items.
- `classification_accuracy_on_decided` = correct exact-label decisions / decided items.
- `outcome_counts` reports each state separately.
- `age_assessment_coverage` = assessed age labels / all supplied gold age labels.
- `age_accuracy_on_assessed` = matching age labels / assessed age labels.
  Missing outputs and `AOA_UNKNOWN` are unassessed. `age_accuracy` retains the
  all-label denominator for compatibility. These are agreement rates with the
  supplied annotations; assessed-label agreement must accompany its coverage.
- `binary_detection` reports corresponding binary accuracies and coverage,
  plus precision, recall, F1, and confusion counts **on decided binary items**.
  Gold items outside the supported binary labels are excluded from that binary
  denominator. Abstentions are counted separately by gold class and are never
  folded into TN or FN.

For example, 36 correct decisions out of 40 decided items in a 50-item corpus
means 90% decided-item accuracy, 80% coverage, and 72% all-item accuracy. An empty
denominator is reported as null, not as a perfect or zero score.

Saved benchmark scores predate this contract and retain their original run
definitions. New evaluations flag records without the current contract version
as `unverified_contract_items`. Resume only reuses current-version, decided,
error-free records with matching text and target ages; older runs need fresh
inference to establish results under these checks.

New batch runs save input and source/prompt SHA-256 hashes and nonsecret settings
in `run_meta.json` before inference. L4 raw responses remain in local run files.
For the repair rationale, frozen baseline and evaluation protocol, see
[the repair review](repair_review.md).

Version 4 adds bounded candidate-identifier normalization. The accompanying L6
wording clarifies the existing ablation criterion without removing its gate.
Historical version-3 runs and comparison results retain their original version
and scores. See [the constraint review](constraint_review.md) for the evidence
and adoption decisions; no new live score is reported for these changes.

Production prompts use abstract rules without fixed evaluation examples.
Development examples are stored separately. See
[the prompt cleanup and controlled comparison](prompt_cleanup_comparison.md)
for overlap checks and the comparison procedure.
