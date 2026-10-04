# Candidate continuation: fixed-prefix comparison

Question: does continuing after candidate-level L5/L6 rejection or uncertainty
help on the current 60-item assignment corpus, with every other rule unchanged?

The control uses `CONTINUE_AFTER_CANDIDATE_REJECTION=false`; the intervention
uses true. Both use identical frozen source, input texts, ages, gold, resources,
stage prompts, thresholds, model gpt-6-luna, and a budget of 24 distinct L4
candidates shared across the item. No corpus-specific targets or answers enter
the implementation or inference. Gold is loaded only by scoring after inference.

Both arms reuse the exact raw SDK responses from the corrected full-assignment
CRACK run dated October 2 locally. Before reusing a response, the entire logged
request (model, messages, response format, temperature when supplied, and output
budget) and stage must match exactly. If the original prefix has remaining
requests, an unexpected request aborts that item. The control may make no new
calls. The intervention may make new calls only after consuming the original
prefix. Original replies, hashes and timings remain recorded separately.

The control must reproduce the original corrected decisions and confirmed
targets on all 60 items. New candidates receive the ordinary unchanged stage
prompts and executable checks. Failed calls remain execution failures; earlier
uncertain candidates remain uncertain unless another candidate completes every
positive check. Search exhaustion produces a negative only when all retrieved
candidates are conclusively rejected. One pass; do not select the best run or
retry a valid verdict.

Metrics: full-gold binary accuracy, precision, recall and F1; coverage/outcomes;
original/rewrite pair success; normalized target agreement; project age-label
agreement and assessment coverage; output-contract failures; and new/cached
calls and tokens. Full outputs and anonymous A/B materials remain available for
human review. A different gold target does not automatically make an analysis
wrong.

This is an intervention on fixed saved first-candidate replies, not a fresh
end-to-end rerun or a generalization/repeatability study. The corpus has already
been inspected. Cached wall times cannot measure end-to-end speed. Report replay
wall time and new request durations separately. No age algorithm or semantic
threshold is chosen from the result.
