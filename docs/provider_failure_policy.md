# Failure, retry and fallback policy

This describes the current detection pipeline, not the retired candidate-search
or standalone-age experiments. A fallback may recover a service request; it
does not turn a negative or uncertain assessment into a positive one.

## Layer behavior

| Stage | Recoverable behavior | Terminal behavior |
|---|---|---|
| L0-pre | Local normalization only | Invalid input records ERROR; detection stages are skipped. |
| L1 | Local regex tokenization and genre routing | An execution error stops dependent work; no model supplies missing tokens or tags. |
| L2 | Local lexical lookup; a missing individual AoA rating stays null | Empty sense retrieval is UNKNOWN; an execution/resource error is ERROR. No model invents dictionary evidence. |
| L3 | Deterministic ordering of retrieved proposals | No candidates is UNKNOWN; execution errors are ERROR. No new candidate is generated to rescue a failed stage. |
| L4 | Provider-specific service recovery below | One shortlist assessment. FAIL, ONE_SENSE_ONLY or INSUFFICIENT_EVIDENCE stops; malformed output is ERROR. No response correction, next candidate request or promotion of the deferred tail. |
| L5 | Provider-specific service recovery below | RESOLUTION_FAIL or INSUFFICIENT_CONTEXT stops; truncation/invalid output is an execution failure. No return to L4 and no substitute scores or context. |
| L6 | Provider-specific service recovery below | SENSES_TOO_CLOSE or an unassessed distinctness result stops; invalid detection output is ERROR. Age preparation failure requests detection only and records the age error. Invalid/missing age data within an otherwise valid detection response is handled by L7. |
| L7 | Local validation of L6's cached estimates | Malformed shared age data fails L7 for the batch; valid UNKNOWN judgments affect their individual ages. Detection remains intact. No model call or synthetic AoA default. |
| L8 | Local aggregation for ages that passed L7 | Other ages retain UNKNOWN appropriateness. Malformed required evidence fails the stage; null axes stay unknown. No model call or automatic safety pass. |
| L0-post | Finalizes the evidence that actually completed | A finalization exception produces EXECUTION_FAILED. Finalization itself adds no request and does not repair prior stages. |

Exceptions and skipped stages discard their partial and downstream results.
An age error can clear L7/L8 but cannot clear completed L4–L6 detection evidence.
For a valid multi-age answer, an uncertain/rejected age does not block another
age that passed comprehension. A malformed shared answer is a stage error,
not an independently validated judgment for its remaining ages.

## Provider-specific service recovery in L4–L6

| Backend and stage | Application retries | Model fallback |
|---|---|---|
| OpenAI-compatible, L4/L5/L6 | At most four backoff iterations, with 2/4/8-second waits. The current helper identifies retryable errors by message text containing `429`, `500`, `502`, `503` or `rate limit`. | None: the selected model/backend is retained. |
| Gemini, L4/L6 | Up to four attempts per configured model, with 2/4/8-second waits after Gemini ServerError. ClientError, including 429, propagates without application retry here. | Advance through that layer's configured `*_MODEL_GEMINI_CHAIN` only after server-error retries exhaust. |
| Gemini, L5 | Up to five attempts per configured model for 500/502/503/504, with 2/4/8/16-second waits. A 429 with a positive reported retry delay can cause one extra retry inside an attempt; spend-cap/zero-quota errors, missing/zero delay and a second 429 fail. | Advance through `L5_MODEL_GEMINI_CHAIN` only after those server-error retries exhaust. Quota failure, invalid JSON and truncation do not switch models. |
| Anthropic, L4/L5/L6 | No application retry loop; SDK behavior applies. | None in the pipeline. |

Gemini's configured primary model is `gemini-3.6-flash`, followed by
`gemini-3.8-flash` in each layer's default chain. An account may lack access to
a configured model; a model/access ClientError is not a trigger for that chain.
Settings and backend selection can change these choices. Auto backend selection
happens before assessment; it is not a switch to another provider after failure.

All production L4/L5/L6 OpenAI-compatible callers set `parse_attempts=1`.
The generic helper still supports two parse attempts for compatibility, but the
pipeline does not use that correction mode. Invalid JSON, extra/missing fields,
invented quotes, inconsistent statuses, refusal and incomplete completion do
not get another semantic assessment or another candidate/model to find a pass.
Switching a Gemini model for service recovery still subjects its answer to the
same local validation.

## Request compatibility and accounting

The OpenAI-compatible helper can retry immediately with adjusted request options
when error text identifies unsupported temperature, token-limit or JSON-format
options. It retains the text, model and assessment task. This parameter
compatibility path is not model fallback and does not waive response validation.
It can add an SDK invocation within a backoff iteration.

OpenAI and Anthropic clients are created without overriding SDK retry settings.
Their installed SDKs may retry HTTP requests internally. Application retry
counters therefore do not count every HTTP attempt, and there is no enforced
whole-item wall-clock deadline. The 2/4/8-second application waits are not a
complete latency bound. Custom/injected clients can have different SDK policies.

With successful first responses and supported request parameters, a completed
positive uses three model requests: L4, L5 and L6, including all requested ages.
L0–L3, L7/L8 and finalization add none. Rejection can stop sooner. Service
retries, SDK retries, parameter compatibility and Gemini model fallback can
exceed three transport requests; they are never requests to improve accuracy.

L4 attempts persist raw responses, model, application retries and fallback flag;
L5 results persist model, application retry count and fallback flag when a result
is returned. New L6 executions persist returned wrapper metadata separately in
`AnalysisRecord.provider_metadata`, including when response validation then
fails. Older L6 records do not contain these counters. The web trace exposes
available L4–L6 metadata after each stage returns; it does not stream individual
retry attempts. A terminal provider exception may occur before counters are
returned, so unavailable metadata remains null rather than implying zero
backoff retries or no fallback. These counters also exclude Gemini L5's
separate positive-retry-delay 429 recovery inside an attempt. The recovery trial's separate SDK observer recorded 115
invocations; the user's repeat count of 116 is inferred from layer records.
Neither count proves a universal transport-request or latency bound.

Implementation: [provider helper](../src/crack/providers.py),
[L4](../src/crack/l4_anchoring.py), [L5](../src/crack/l5_resolution.py),
[L6](../src/crack/l6_distinctness.py), [runner](../src/crack/runner.py),
[response contracts](response_validation.md) and [age evidence](age_evidence.md).
