# Frozen full-assignment comparison, version 1

## Question and arms

Compare the current CRACK implementation with one stateless direct-LLM analysis on the existing 60 texts and all 180 requested age labels. This is a comparison of complete configurations. It does not isolate the causal effect of layering; candidate retrieval, routing, semantic gates and age algorithms also differ.

Model: gpt-6-luna in both arms, with temperature omitted as in the current pipeline. CRACK source and prompts, direct and reviewer prompts, inputs, gold, this protocol and the experiment runner are copied and hashed before inference. CRACK's thresholds, candidate budget (24), scope policy and gold remain unchanged. One fresh pass per arm, concurrency 8, fixed arm order chosen before inference from seed 20261002. No prompt revision, best-run selection or selective replacement using outcomes. Gold is loaded only after both arms finish.

## Shared resources and validation

Both arms use the identical frozen Kuperman word-level AoA CSV and its existing lookup function. The direct request receives an exhaustive lookup table for words in the input and dictionary-recognized literal compound parts; missing values are explicit. CRACK can additionally query its generated sense descriptions through the same lookup function, as it currently does. This difference in which queries each algorithm chooses is retained and documented, not claimed to be an identical-prompt causal ablation. No target-word hint, gold sense or age label is supplied to the direct model.

The common output contract checks required fields, enum values, a real target substring, two different nonempty meaning descriptions for PUN, nonempty exact source quotations, and consistent PUN/non-PUN output structure. Age entries, when supplied, require valid fields and enum values. Source citations must reproduce a real shared lookup entry; an absent citation is not fabricated by an adapter. A faithfully referenced null/miss entry remains missing information, is allowed as evidence of uncertainty, and receives no numeric-source credit. CRACK's additional native semantic gates remain active. Invalid direct replies may repeat the identical request, at most two format attempts, with up to four transport attempts each; invalid evidence is never corrected into a passing quotation. All attempts are retained. Failed items remain in all-item denominators. Age omissions are reported separately and never silently filled from the gold.

Current CRACK uses deterministic L7/L8 because its runner does not supply an LLM client to those functions. Its estimated sense ages and metalinguistic floors are retained as estimates; the adapter does not add citations to make them look sourced. For a rejected candidate, diagnostic reasons are preserved without presenting two candidate senses as a confirmed joke.

## Predeclared metrics

- Binary detection: all-item accuracy, precision, full-gold recall/F1, decision coverage and accuracy among decisions. Unresolved gold-positive items count as misses in full-gold recall/F1; unresolved negatives are reported separately.
- Exact project label agreement (secondary): distinguish homograph from compound split and project non-pun labels; do not equate this to the primary binary metric.
- Paired success: both the original Jxx and rewritten Dxx correctly classified, out of 25 pairs. Report original, rewrite and ordinary-control accuracy separately.
- Target localization: exact normalized target agreement on all 25 gold-positive inputs and among true-positive decisions. Meaning correctness is reviewed, not evaluated by literal definition-string equality.
- Age labels: agreement and assessment coverage across all 180 project labels; separately on the 75 gold-positive age labels, and the common true-positive subset. These measure annotation agreement, not child comprehension validity. Unknown/missing assessments remain unassessed. There is no appropriateness gold in this corpus; do not invent appropriateness accuracy.
- Source support: number of age explanations containing programmatically verified AoA citations, with all 75 gold-positive age labels as denominator. This is traceability of vocabulary evidence, not empirical confirmation of a sense or complete joke's acquisition age.
- Runtime: fresh batch wall time, complete per-item latency (including retries), median/P95 and total recorded API usage/calls. Lexical resource initialization and shared input-table construction happen before timing. Native SDK calls are observed without modifying their prompts or responses; SDK-internal transport retries may be unobservable.

## Blind review

Normalize output presentation without rewriting substantive answers. Remove system names and internal layer labels; randomly place systems A/B, balanced 30/30, with a frozen seed. Neither original corpus IDs nor gold are sent to the reviewer. Preserve private identity mapping separately from anonymous packets. Fixed 0–2 rubric: detection reasoning, meanings/evidence, humor explanation, age evidence, content appropriateness. The last three are not applicable to inputs the reviewer independently judges non-puns. A missing answer on a genuine pun scores zero rather than being excluded.

Optionally use an independent stateless call to the same model as an automated blind reviewer; clearly label the result LLM-assisted, not human. Run every packet again with A/B swapped to measure order stability; keep both results, average dimensions, and mark inconsistent preferences instead of selecting a preferred order. Retain packets and an empty human-review CSV for independent review. No single automated review establishes factual age validity or freedom from model/style bias.

## Decision rule

Report all dimensions. A detection winner alone is not a complete-task winner. Recommend a configuration for this assignment only with its explanation/evidence/age findings stated. If dimensions trade off or human review is outstanding, give a conditional recommendation and the missing evidence. Do not collapse unlike measures into an arbitrary overall accuracy.

## Version 1 execution correction

The first run's validator erroneously rejected exact null/miss references. The frozen original protocol, validator and scores are retained in the run. The clarified rule above fixes this generic implementation error; it does not change a missing value into a known AoA. All original replies were uniformly revalidated, taking the earliest valid response. All changed anonymous cards were reviewed again in both orders. See `docs/full_assignment_comparison.md` and the run's `corrected_validation/` audit trail for the original and corrected results. This amendment was made after inference and is identified explicitly rather than described as part of the original frozen implementation.
