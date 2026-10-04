# Contextual wordplay and ablation: fixed protocol v1

## Intervention

One abstract clarification of L6's existing ablation question. Establish the
claimed interaction in the original text before crediting its removal by a
single-sense substitution. Incidental second-domain objects and dictionary
multiplicity cannot establish that interaction. Indirectly evoked readings
remain eligible. Keep conceptual distinctness separate from ablation support.

The baseline is the completed candidate-continuation configuration. Both arms
have the same model, source, L4/L5 prompts, quotes/field checks, thresholds,
24-candidate budget, search policy, resources and age algorithms. Only the L6
prompt path differs. No new response fields or automatic semantic correction.
Transport/format/evidence failure remains execution failure.

## Development and confirmation cases

`corpus/prompt_development/contextual_v1/` supplies 24 newly authored stage cases.
Six development families and six separate confirmation families each contain
one intended pun and one incidental-topic control. Inputs, proposed senses,
quotes, expectations and family allocation are frozen before inference.
Expectations are provisional project annotations; human adjudication is pending.

Both prompts receive the same target and proposed readings, without labels or
annotation notes. Run one fresh pass in each arm. Report positive passes,
negative false passes, errors and all failures separately for both splits.
These evaluate L6 given hypotheses, not candidate retrieval, age or full-task
accuracy. Neither set is inserted into production prompts. No result-guided
prompt revision, relabeling, example replacement or best-run selection occurs
in this experiment. Confirmation outcomes may not guide revisions here.

## Current course corpus

The existing 60 texts and gold are frozen and already developer-inspected.
They are a regression comparison, not an unseen benchmark. Reuse only
per-item SDK replies with identical stage and complete logged request fields,
at most once each and in original request order when identical requests recur.
The baseline must exactly reproduce all 60 substantive outputs and all 409
saved calls with zero new inference before the treatment starts.

Treatment L6 requests are fresh because the prompt changes. Unchanged L4/L5
requests can reuse the identical saved replies. New branches after rejection
make fresh requests when no identical reply is available. Preserve request IDs,
raw responses, errors, candidate ledger and configuration hashes. Report cached
versus new usage separately. Replay duration is not fresh full-run latency.

Score unchanged detection metrics, 25-pair success, exact normalized targets,
coverage and age-label agreement. Abstentions remain misses in all-item accuracy
and positive recall. Do not count an abstained negative as a correct negative.
Do not modify gold after inspecting outputs.

## Review and adoption

Review every changed assignment output in both anonymous A/B orders using the
existing full-assignment rubric. The reviewer sees no identity, corpus ID, gold
or aggregate metrics. Preserve disagreements and failed reviews; human review
remains necessary. This selective review describes changed outputs, not a new
60-case aggregate quality score.

Before adoption, require no new contract failures; no loss of intended-positive
passes on either new split; fewer negative false passes in at least one split
and no increase in the other. On the course regression require accuracy at least
55/60, F1 at least the continuation baseline (90.20%), pair success at least
21/25 and coverage at least 58/60. Reviewer-supported contextual regressions
must be reported and examined. These are experiment acceptance criteria, not
new runtime decision thresholds.

If the draft fails these criteria, retain it and its results as an experiment;
leave the production prompt at baseline. Do not tune it again against this
confirmation pass. A future revision needs development evidence and a new
independent confirmation set.

This protocol uses frozen inputs, scoped comparisons and review of automated
judgments, following [OpenAI's evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices).
