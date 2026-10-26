# Engineering fixes after the resource-refresh runs

These changes address execution and scoring reliability. The semantic prompt
files, model selections, candidate budgets, phonetic thresholds and L5 decision
thresholds are unchanged. Existing saved runs retain their original results;
no live inference has been repeated for this patch.

## Credential preflight

The command-line batch and single-text entry points now check credentials before
executing layers or creating run output. Missing or whitespace-only credentials
produce an argument error (exit code 2) naming the relevant environment variable.
Provider-specific aliases and generic fallback credentials remain supported.
The check is local: it does not establish that a key is valid, funded or allowed
to access the selected model. Authentication and transport failures still have
their existing runtime handling. The web server startup is unchanged. The
programmatic `runner.run()` API retains per-item error recording; callers can
use `providers.check_credentials(backend, settings)` before invoking it.

## L4 strict OpenAI response schema

L4 now sends the existing eleven-field Pydantic contract to the `openai` backend
as `response_format.type=json_schema`, with `strict=true`, all fields required,
explicit nullable fields and `additionalProperties=false`. This follows the
[OpenAI Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat).
This directly addresses J21's extra `unused` field. Local field, quote and
phonetic validation remains authoritative, including rejection of extra fields.

An unsupported strict schema raises an error instead of silently falling back
to unconstrained output. Parameter compatibility retries retain the schema.
Other compatible backends retain their existing JSON mode; Gemini already has
a response schema. L5 and L6 output requests are unchanged in this patch.
Custom endpoints configured under `openai` must support the strict request;
use the `compatible` backend for an endpoint requiring the legacy JSON mode.

## Soundalike detection report

`scripts/evaluate_soundalike.py detection` now computes confusion counts and
precision/recall/F1 on explicit PUN/NON_PUN decisions only. It separately prints
all-item binary accuracy and unresolved counts by reference class. Failed,
abstained, out-of-scope and missing records remain in the all-item denominator
and cannot count as correct negatives or complete a correct matched pair.
The canonical `crack.corpus.evaluate_run` metrics were already separate and
are unchanged. This fix does not retroactively improve inference accuracy.

Use fresh output roots for post-fix inference, such as
`runs/engineering_fix_soundalike` and `runs/engineering_fix_regression`.
Source fingerprints differ from the prior runs, so their records should not
be resumed under the changed implementation.

## Verification

The full offline suite passes: **578 passed, 10 live tests deselected**. It
covers missing and blank credentials, fail-fast CLI behavior with no output
directory or layer execution, strict L4 request fields, preservation of the
schema during parameter retries, refusal to downgrade an unsupported schema,
continued local rejection of `unused`, and failed/abstained/out-of-scope/missing
negatives in the paired scorer. Two existing FastAPI lifecycle deprecation
warnings remain.

Rescoring `runs/resource_refresh_soundalike/20261026T014933Z/records.jsonl`
still gives 71/79 all-item binary accuracy and TP 32 / FP 4 / FN 4 / TN 39.
Because that run has no unresolved items, its detection metrics do not change.
The strict schema still needs validation against a fresh real provider run;
offline request tests do not establish that J21 will receive a correct
semantic decision.
