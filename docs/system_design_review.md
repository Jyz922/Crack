# System design review — 3 October 2026

Historical review of contract version 5. The current contract and layer recovery
behavior are documented in [response validation](response_validation.md) and
[the failure policy](provider_failure_policy.md). The later
[October 4 comparison](corpus_recovery_20261004.md) evaluates the current design.

This review checks evidence handling, execution and scoring across L0–L8. It
removes restrictions that do not follow from the assignment while preserving
source quotations, distinct meanings and contextual support. Detection response
contract version 5 records the revised L5/L6 rules. No extra model stage was added.

## Changes

| Part | Finding | Revision |
|---|---|---|
| L0-post | Co-occurring soundalike words could override a completed homograph analysis. Their presence does not establish the mechanism. | Removed the fixed word-pair verdict heuristic. Scope follows assessed evidence. |
| L1 → L5 | A question without a separate answer was forced through answer-specific checks. A question can itself contain wordplay. | Route self-contained questions through the existing general wordplay branch. L1's surface classification remains a routing hint. |
| L2 | Removing punctuation during tokenization could form a multiword proposal across sentence boundaries. | Keep a phrase proposal only if its surface wording occurs in the source. Individual-word retrieval continues. |
| L5 | Weighted scores could conceal an explicit contradiction in a relation necessary for the proposed wordplay. | Record `context_consistent`; a false finding rejects resolution regardless of the average. The explanation identifies the conflicting wording and relation. |
| L5 prompts | Requiring enough evidence for every optional feature could create needless abstentions. | Missing causality, a shared agent or an answer turn is not automatically insufficient evidence. Ordinary conventional readings can be inferred from their cues. |
| L6 | Mutual exclusion was required even when distinct meanings describe coexisting events or properties. | Require material semantic difference and different paraphrases. `suppresses_other` becomes a diagnostic, not a gate. |
| L7 | A dimension could invite invented background prerequisites just to fill the field. | Explicitly permit “no extra background knowledge needed,” with its reason. Missing word ratings retain null citations and can support explained contextual estimates. |
| L7/L8 execution | Detection-only inputs with no requested ages could enter age validation unnecessarily. | Skip age calls when no ages are requested. Age-stage failure still preserves detection and leaves age outputs unknown. |
| Output | The web target was read from a nonexistent field or a lexical-ranking fallback. | Display the assessed `L4.target_term` directly. Unconfirmed results continue to hide punchlines and dual readings. |
| Resume | Version numbers alone did not prevent mixing changed prompts or model/settings. | Require matching source/prompt hashes and nonsecret settings before reusing records. Stop incompatible resume before new calls. |

An explicit contradiction concerns a relationship required by the claimed
wordplay. Figurative language, a playful premise, and two descriptions that can
coexist do not fail that check by themselves. Optional features contribute their
existing scores; they are not independent mandatory gates.

## Rules retained

- L4 source quotations remain exact; candidate spellings and supplied splits are checked.
- Invalid or missing response fields are rejected. A correction may supply a new response; the program never manufactures passing evidence.
- A completed negative is different from missing context or an execution failure.
- L6's controlled rewrite still assesses whether the specific two-meaning contrast disappears. Other situational humor may remain.
- Age evidence covers the whole text. Word-level AoA citations remain separate from estimated sense familiarity and child understanding.
- Numeric thresholds, weights, candidate budget defaults, model configuration, corpus texts and gold labels are unchanged.
- Production prompts contain abstract rules; no evaluation sentences or their answer demonstrations were added.

## Existing 60-item evidence

The saved October 3 detection prefix used by the age comparison has **59/60
decisions (98.33% coverage)**: 26 PUN, 33 NON_PUN and one insufficient-evidence
result, with no execution failures. Its binary accuracy is 55/60 (91.67%). The
corpus contains 25 gold positives and 35 non-pun controls, so a negative finding
is often the intended successful outcome.

The unresolved item, J24, was rejected by L5 because its question had no separate
answer. The revision addresses that text form generally; it neither hard-codes
J24 nor supplies its correct answer. Its new model judgment has not been measured.
See the [saved detection counts](age_aggregation_comparison_20261003.json).

Those figures belong to the earlier version. The saved records remain readable;
they are not relabeled as version-5 outputs or used to claim a new score.

## Offline verification

The verification covers input/scope rules, surface routing, lexical retrieval and
ranking, all four L5 forms, accepted/rejected/unknown L6 findings, age citations
and aggregation, provider parsing, final-state scoring and frontend payloads.
The current regression selection passed **243 tests**.

New cases include:

- Supported responses can pass every L5 form; a standalone question uses the general branch.
- Strong contrast and answer scores can pass with absent optional causal/agent/tense features.
- An explicit required-relation conflict cannot be averaged into a pass.
- Distinct meanings can pass with true, false or unknown mutual suppression; identical paraphrases and false material difference still fail.
- Unknown findings and malformed replies remain separate from confirmed negatives in an end-to-end run and its evaluation.
- Null AoA ratings remain null; a known estimated barrier and another unknown dimension are both retained.
- Age rejection requires its own evidence; an unassessed axis cannot become default approval.
- A corrected age citation retains the rejected raw reply and the replacement response.
- Sixty **synthetic** inputs complete through L0–L6 with eight concurrent workers, unique records and compatible resume without further model calls.

The tests use synthetic responses and mocked provider clients; they verify program
rules and execution, not fresh model accuracy. They do not exercise live provider
availability or replace the human review of semantic explanations.

The README gives the explicit offline test selection. Older L5–L8 test files
contain fixtures for earlier contracts and are outside this selection; this is
not a claim that the entire legacy suite passes. The design snapshot, input hashes
and verification log are saved under `runs/system_design_review/`; the current
run is identified by `current_run.txt`. No new API calls were made for this review.

## Practical interpretation

Acceptance follows evidence relevant to the text. There is no target quota of
positives or abstentions, and thresholds were not adjusted to obtain a preferred
score on these 60 items. A fresh full run is needed to measure how the revisions
affect accuracy and decision coverage. Model-based meaning connections and age
estimates remain judgments; valid response structure alone does not prove them.
