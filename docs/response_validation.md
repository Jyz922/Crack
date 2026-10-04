# Response validation and terminal states

Current detection contract: `6`; candidate-selection policy: `4`.
Every model answer is checked locally before it becomes a layer result.
The pipeline does not repair an invalid response with another model request.

## Layer states and stopping

| State | Meaning | Dependent work |
|---|---|---|
| PASS | The layer completed its required positive check | Continue |
| FAIL | The completed check rejected the proposed analysis | Stop |
| UNKNOWN | Context or evidence is inadequate | Stop |
| ERROR | Execution failed, output was truncated, or validation rejected it | Stop |
| SKIPPED | A dependency did not pass or the task was not requested | No assessment |

Detection failure/abstention skips later semantic and age layers. The finalizer
always runs. An exception or skip discards the stage's partial and downstream
results. Age failures affect age outputs only; completed detection is preserved.
For multiple requested ages, L8 processes only ages that passed comprehension;
other ages retain unknown appropriateness.

## Essential response checks

- **L4:** required fields and supported status values; the supplied candidate
  identifier; real verbatim source quotes; two described readings and an
  explicit resolving sense for PASS. A compound split must match a supplied
  split proposal. Missing facts are not inferred from defaults. Raw responses
  and rejection reasons remain in `l4_attempts`.
- **L5:** required finite subscores in [0, 1], an explicit evidence finding and
  context-consistency finding. A relation necessary for the proposed wordplay
  cannot contradict the source. An unassessed result uses null scores and a
  reason. Self-contained questions do not require an invented answer turn.
- **L6:** materially different meanings, distinct paraphrases and an explicit
  result. Missing assessment stays unknown. Compound splits are checked too.
  Mutual suppression and the historical ablation field are diagnostics, not
  positive gates. No controlled rewrite is required.
- **Final positive:** L4 PASS, L5 RESOLUTION_PASS and L6 SENSES_DISTINCT must all
  be present and valid. Skipped or unknown evidence never becomes positive.

L4 compares the original shortlist (default eight terms) in one request and
returns the strongest target's evidence. The target must be supplied and its
quotes/split must validate. Rejection, UNKNOWN or invalid output stops; no
corrective request or next-candidate search follows. `considered_terms` records
the offered list; only the chosen result has individual validated evidence.
L5/L6 rejection never resumes search. Dictionary tails are metadata only, and
exhaustive rejection is not a condition for a bounded negative. The candidate
budget controls the number of terms offered, not additional requests. The
legacy continuation flag is a compatibility no-op.

Existing transport retries for transient provider errors remain. These are
separate from response correction or requests for additional semantic evidence.
Normal-response request bounds are L4 <= 1, L5 <= 1, L6 <= 1, L7/L8 = 0.
OpenAI-compatible calls retain their selected model; Gemini's configured chain
is used only after its server-error attempts exhaust. SDK and request-option
compatibility retries can add calls; counters do not cap HTTP attempts or total
latency. See [the layer/provider recovery policy](provider_failure_policy.md)
for exact triggers and terminal behavior.

## Final outcomes

| State | Meaning |
|---|---|
| PUN | All required positive detection checks completed |
| NON_PUN | A completed check rejected the proposed wordplay in the bounded search |
| INSUFFICIENT_EVIDENCE | Context or a required assessment is missing |
| EXECUTION_FAILED | Execution or response validation failed |
| OUT_OF_SCOPE | A different mechanism needs assessment |

The last three states require review. They do not receive invented senses,
default confidence or safety passes. L5's resolution score is a stage score,
not a calibrated probability of correctness.

## Age assessment

Age response contract `3`, aggregation version `4`. L6's existing request
returns one compact understanding estimate and separate content/inference
findings per requested age. L7/L8 validate and aggregate these locally with no
provider requests. Missing/malformed data fails age assessment; UNKNOWN/null
remains unknown. AoA citations come from local lookup, never model-written
numbers. Numeric sense ages and fixed genre age floors are not invented.
The web interface requests only the selected age. See [age evidence](age_evidence.md).

## Evaluation and provenance

Evaluation includes every gold ID. Missing predictions are failures; duplicate
or unknown IDs are rejected. Decision coverage is decided/all items, all-item
accuracy is correct/all items, and decided-item accuracy is correct/decided
items. Unresolved outputs remain separate from negative predictions. Binary
precision, recall and F1 are reported on decided binary items, with abstentions
counted separately by gold class. Empty denominators are null.

Age agreement accompanies assessment coverage. Missing outputs, AOA_UNKNOWN
and unknown appropriateness are unassessed; no age accuracy improvement is
established by offline contract tests.

Runs save input/source/prompt hashes and nonsecret settings before inference.
Resume requires matching provenance, text, ages, current contract versions and
an error-free decided record. Records with UNKNOWN traces are rerun. Historical
scores keep their original definitions and cannot establish current accuracy
or latency. Older continuation, ablation and five-dimension age experiments
are historical records; reproduce them with their frozen source snapshots.

## Status reference

These values include compatibility labels retained for saved records. Current
final outcomes and their meaning are described in the result-state table above.

| Field | Values |
|---|---|
| `ScopeLabel` | `HOMOGRAPH`, `COMPOUND_SPLIT`, `OUT_OF_SCOPE_HOMOPHONE`, `OUT_OF_SCOPE_NONLEXICAL_JOKE`, `NO_SCOPE_MECHANISM` |
| `Genre` | `QA_RIDDLE`, `DEFINITIONAL_ONELINER`, `DIALOGUE_MISUNDERSTANDING`, `DECLARATIVE` |
| `AnchoringStatus` | `PASS`, `FAIL`, `ONE_SENSE_ONLY`, `INSUFFICIENT_EVIDENCE` |
| `AnchorRelation` | `separate_contexts`, `resegmentation`, `speaker_mismatch` |
| `ResolutionStatus` | `RESOLUTION_PASS`, `RESOLUTION_FAIL`, `INSUFFICIENT_CONTEXT`, `TRUNCATED_OUTPUT`, `EXECUTION_FAILED` |
| `DistinctnessStatus` | `SENSES_DISTINCT`, `SENSES_TOO_CLOSE`, `L6_SKIPPED_NO_PARAPHRASE` |
| `AmbiguityAblation` | `SUPPORTED`, `UNSUPPORTED`, `SKIPPED` |
| `ComprehensionStatus` | `FULLY_COMPREHENSIBLE`, `PARTIALLY_COMPREHENSIBLE`, `SENSE_B_TOO_ADVANCED`, `WORDPLAY_SKILL_TOO_ADVANCED`, `AOA_UNKNOWN` |
| `AgeAppropriatenessVerdict` | `UNKNOWN`, `FULLY_AGE_APPROPRIATE`, `CONTENT_OK_INFERENCE_TOO_ADVANCED`, `VOCABULARY_TOO_ADVANCED`, `CONTENT_NOT_APPROPRIATE` |
| `MainClassification` | `VALID_HOMOGRAPH_JOKE`, `VALID_COMPOUND_SPLIT_JOKE`, `NO_AMBIGUITY_FOUND`, `ONE_SENSE_ONLY`, `ANCHORING_FAIL`, `RESOLUTION_FAIL`, `SENSES_TOO_CLOSE`, `OUT_OF_SCOPE_HOMOPHONE`, `OUT_OF_SCOPE_NONLEXICAL_JOKE`, `INSUFFICIENT_EVIDENCE`, `EXECUTION_FAILED` |
| `DetectionStatus` | `PUN`, `NON_PUN`, `INSUFFICIENT_EVIDENCE`, `EXECUTION_FAILED`, `OUT_OF_SCOPE` |
