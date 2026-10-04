# October 4 corpus recovery

The revised pipeline recovered exact classification agreement from **47/60
(78.3%) to 55/60 (91.7%)** on the same project corpus. Binary accuracy recovered
from **49/60 (81.7%) to 56/60 (93.3%)**. Fail-fast behavior, explicit unknown
outcomes, strict response validation and service retry/fallback remain enabled.

The initial complete recovery pass and a fresh user rerun both achieved these
classification scores on the same source. This is a previously inspected
regression corpus, not an unseen benchmark. Both passes are retained; no
answers were selected between runs, gold labels edited, or thresholds tuned
after scoring.

## Changes

1. **L4 chooses the target in one request.** It compares the original top-eight
   shortlist against the whole text, then returns one target and its contextual
   evidence. This replaces separate candidate requests and avoids accepting a
   weak candidate before considering the word that explains the joke. The
   target must belong to the supplied shortlist; exact quotation and response
   field checks still apply. Rejection, uncertainty or malformed output stops
   the pipeline without another candidate request.
2. **L6 compares meanings at the appropriate level.** A conventional second
   meaning can be evoked by context without describing an event that actually
   happens in the sentence. The prompt now distinguishes that from invented
   events, unrelated topics and unsupported meanings. Ablation is diagnostic;
   it does not add a model call or override detection.
3. **Age estimates distinguish sense-specific barriers.** The compact L6
   response can identify difficulty with sense A or sense B. L7 can again
   return `SENSE_B_TOO_ADVANCED`. Word familiarity is not treated as proof that
   a child understands an idiomatic or specialist meaning. L7/L8 remain local.

L5 weights and thresholds, corpus inputs, requested ages, and gold labels are
unchanged. UNKNOWN/ERROR still stop dependent work. Invalid responses are not
repaired or retried for a different semantic answer. Existing transport retries
and provider fallback still handle supported service failures.

## Complete-corpus comparison

Both runs used OpenAI `gpt-6-luna`, the same 60 texts and age lists, and concurrency
8. L3's original shortlist stayed at eight. The earlier configured L4 cap was
24, but its trace records show no search outside the original shortlist; the
new cap is eight and limits candidates supplied to a single request.

| Metric | Before: `20261004T214044Z` | Recovery: `20261004T220004Z` |
|---|---:|---:|
| Exact classification, all items | 47/60 (78.3%) | 55/60 (91.7%) |
| Binary accuracy, all items | 49/60 (81.7%) | 56/60 (93.3%) |
| Decision coverage | 54/60 (90.0%) | 60/60 (100.0%) |
| Exact classification, decided items | 47/54 (87.0%) | 55/60 (91.7%) |
| Binary accuracy, decided items | 49/54 (90.7%) | 56/60 (93.3%) |
| PUN / NON_PUN / insufficient / failed | 20 / 34 / 5 / 1 | 27 / 33 / 0 / 0 |
| Age agreement, all original labels | 42/180 (23.3%) | 51/180 (28.3%) |
| Age assessment coverage, all original labels | 59/180 (32.8%) | 73/180 (40.6%) |
| Age agreement, assessed original labels | 42/59 (71.2%) | 51/73 (69.9%) |
| Age agreement, all gold-pun labels | 37/75 (49.3%) | 46/75 (61.3%) |
| Age assessment coverage, gold-pun labels | 53/75 (70.7%) | 67/75 (89.3%) |
| Age agreement, assessed gold-pun labels | 37/53 (69.8%) | 46/67 (68.7%) |

UNKNOWN and execution failures remain in the all-item denominators. Zero
unknowns in this pass means that every item produced a decision, not that the
unknown/error paths were disabled. Recovery precision is 24/27 (88.9%), recall
24/25 (96.0%), and F1 92.3%.

The original age denominator includes 105 labels on literal controls that the
current wordplay-age pipeline does not assess. The additional 75-label
`age_gold_puns` view includes every annotated pun, including missed puns. It
does not replace or change the original 180-label metric. **Age agreement rose
mainly because detection coverage recovered; conditional age agreement did
not improve.** Age discrimination remains a separate weakness.

## Fresh user rerun — `20261004T222826Z`

The user reran all 60 items after the recovery pass. Source hashes, effective
configuration, input texts, requested ages and gold labels match the first
recovery pass. No production code or prompts changed between these runs.

| Metric | First recovery | Fresh user rerun |
|---|---:|---:|
| Exact classification, all items | 55/60 (91.7%) | 55/60 (91.7%) |
| Binary accuracy, all items | 56/60 (93.3%) | 56/60 (93.3%) |
| Decision coverage | 60/60 (100.0%) | 60/60 (100.0%) |
| Age agreement, all original labels | 51/180 (28.3%) | 53/180 (29.4%) |
| Age assessment coverage, all original labels | 73/180 (40.6%) | 74/180 (41.1%) |
| Age agreement, assessed original labels | 51/73 (69.9%) | 53/74 (71.6%) |
| Age agreement, all gold-pun labels | 46/75 (61.3%) | 48/75 (64.0%) |
| Age assessment coverage, gold-pun labels | 67/75 (89.3%) | 67/75 (89.3%) |
| Age agreement, assessed gold-pun labels | 46/67 (68.7%) | 48/67 (71.6%) |

The repeated aggregate scores support recovery on this corpus, but predictions
still vary. Three exact classifications changed:

- J06 changed from `RESOLUTION_FAIL` to the correct `VALID_COMPOUND_SPLIT_JOKE`.
- J13 changed from `VALID_HOMOGRAPH_JOKE` to `RESOLUTION_FAIL`; both disagree
  with the annotated compound split, and the latter is also a binary miss.
- D12 changed from `ONE_SENSE_ONLY` to `RESOLUTION_FAIL`; it remains binary
  negative but no longer matches the exact gold label.

D03, D17 and D24 remained false positives in both passes. The user rerun's five
exact-label mismatches are J13, D03, D12, D17 and D24. No annotation changes
were made to remove these errors. Across the 180 original age labels, 22
predictions changed between passes, so the small age-agreement improvement
does not establish improved age discrimination.

The rerun implies **116 normal requests** from recorded attempts/results:
L4 60, L5 29, L6 27. No L4/L5 provider retries were logged. This run did not
instrument SDK invocations; its inferred request count excludes unrecorded
transport retries. Average summed per-item trace duration was **15.16 seconds**
and the median **11.56 seconds**, again with concurrency eight. These remain
descriptive timings rather than a controlled latency benchmark.

See the [user-rerun evaluation](evaluations/repeat_20261004/evaluation.json)
and [repeat audit](corpus_recovery_repeat_20261004.json) for the complete metrics,
source hashes, classification changes and age-label changes.

## Calls and response time

The recovery observer logged **115 SDK calls: L4 60, L5 28, L6 27**, with no SDK
errors or logged provider retries. Normal successful execution uses at most
three model requests per item, including all requested ages. Earlier records
imply 358 normal requests: L4 305, L5 28, L6 25. That earlier count is inferred
from attempts/results and excludes any unrecorded transport retries; the
recovery count is directly observed at the SDK boundary.

Summed per-item stage duration averaged **16.12 seconds**, compared with
**29.79 seconds** before; the median was **12.67 versus 28.41 seconds**. Both
runs used concurrency eight. These are descriptive trace timings from runs
at different times, including local work and resource initialization, not a
controlled provider-latency benchmark. No claim of a fixed speedup follows
from this single comparison.

## Initial recovery classification errors

| Item | Gold | Prediction | Selected target | Binary correct |
|---|---|---|---|---|
| J06 | `VALID_COMPOUND_SPLIT_JOKE` | `RESOLUTION_FAIL` | `exit` | No |
| J13 | `VALID_COMPOUND_SPLIT_JOKE` | `VALID_HOMOGRAPH_JOKE` | `room` | Yes |
| D03 | `ONE_SENSE_ONLY` | `VALID_HOMOGRAPH_JOKE` | `trunk` | No |
| D17 | `ONE_SENSE_ONLY` | `VALID_HOMOGRAPH_JOKE` | `mail` | No |
| D24 | `ONE_SENSE_ONLY` | `VALID_HOMOGRAPH_JOKE` | `stories` | No |

These cases were retained as errors. No item-specific exceptions or changes to
annotations were added after inspecting this pass.

## Audit and reproduction

- [Machine-readable comparison](corpus_recovery_20261004.json): counts, input,
  gold, record and source hashes, remaining errors and protocol limitations.
- [Recovery evaluation](evaluations/recovery_20261004/evaluation.json)
  and [published per-item records](evaluations/recovery_20261004/records.jsonl).
- [Baseline evaluation](evaluations/reliability_baseline_20261004/evaluation.json).
- [Published-record format and offline verification](evaluations/README.md):
  declared omissions, original/published hashes and unchanged metric checks.
- The local trial directory preserves frozen source/resources, blind inputs,
  gold labels, the plan written before inference, and SDK request/response
  records without credentials. Its `summarize_trial.py` regenerates the
  original comparison offline. Publication later changed only the unused
  SemEval report/evaluator output; all detection/age source and prompts still
  match the frozen, evaluated implementation.

Offline verification passed **402 tests**, with 10 live-call tests deselected
and two existing FastAPI deprecation warnings. Tests cover bounded shortlist
selection, strict quotes/fields, fail/unknown stopping, provider retries,
shared age dispatch and age barrier mapping. The real corpus pass supplies
the accuracy evidence separately from those tests.

Use the [README corpus command](../README.md#test-the-current-project-corpus)
for another fresh pass. Both saved passes are published; no additional provider
calls were made while preparing these records and documentation for GitHub.
