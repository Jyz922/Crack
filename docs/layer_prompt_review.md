# Layer and prompt review — 3 October 2026

This historical review checks the October 3 implementation for unsupported defaults,
invented evidence and instructions that presume a successful joke analysis.
It makes no new accuracy claim and adds no evaluation examples, thresholds or
pipeline layers. The corpus and gold remain unchanged.

Current contracts and recovery behavior are specified in
[response validation](response_validation.md) and
[the failure policy](provider_failure_policy.md).

## Layer review

| Layer | Evidence and output | Handling of unsupported claims |
|---|---|---|
| L0 | Normalized input; final scope and decision | Input validation is separate from semantic judgment. A final positive requires the existing completed L4–L6 findings; errors and incomplete searches have separate outcomes. |
| L1 | Regex tokens and genre routing | Genre is a routing hint, not proof that an input is a joke. Regex does not invent POS tags or lemmas. |
| L2 | WordNet entries, SemCor counts and word-level AoA | Dictionary senses and splits are proposals. Missing ratings stay null; match methods distinguish original ratings from derived values. |
| L3 | Candidate ordering and retained search tail | Priority scores are search heuristics. Zero observed counts do not establish balanced use, and candidate rank does not establish wordplay. |
| L4 | Two proposed readings with exact source cues | Same written candidate, source quotes, required fields, statuses and supplied splits are checked. Conventional indirect readings need cues; an invented event or differently spelled soundalike cannot establish homographic PASS. |
| L5 | Form-specific resolution scores and reasoning | Readings and role labels are proposals. The prompt no longer opens by assuming the text is a joke; negation, causal direction and actual wording must support the claim. Existing null-score abstention remains available. |
| L6 | Distinct paraphrases and proposed controlled rewrite | Upstream acceptance is not proof of meaning truth. Rewrites are proposed counterfactuals, not source quotations or independent measurements. Missing evidence retains the existing skipped/unknown result. |
| L7 | Whole-text vocabulary citations; five age dimensions | Citations must match the supplied table exactly. Word-level ratings do not become measured sense ages; contextual estimates and UNKNOWN dimensions stay explicit. |
| L8 | Per-age content/inference axes and reasons | Content rejection needs a source quotation; inference rejection needs a prerequisite. Null axes cannot be filled into passes. There is no generated universal content-age threshold or safety guarantee. |

## Changes from this review

1. **Neutral L5 wording.** The four form prompts treat supplied readings as
   proposals and forbid invented replies, participants, intentions or context.
   A definition-style input can use ordinary lexical ambiguity; it is not forced
   to invent a compound split. Existing score fields and weights remain intact.
2. **Literal prompt rendering.** L4 and L6 substitute template variables once.
   Braced strings inside user text or meaning descriptions are preserved rather
   than being replaced as later template fields. L6 preserves empty source
   anchors instead of filling them with the candidate word. L5/L6 use the L4
   target before consulting legacy candidate metadata.
3. **L6 claim boundaries.** The prompt distinguishes proposed rewrites from
   measured results and says the sample positive flags are format examples.
   Its provider schema now rejects extras, matching the existing runtime validator.
4. **No automatic explanation story.** Backend and frontend display the returned
   L5 explanation. If it is absent, they show that it was not returned instead
   of constructing a setup, semantic shift, sense order or punchline explanation.
5. **Evaluation reporting.** Dated CRACK results retain their task, corpus,
   saved source version and reproduction commands. Structural validation does
   not establish performance on a new dataset.

The old layer-wrapper docstring incorrectly described implemented layers as
stubs; it now describes the actual execution wrappers.

## What these checks establish

The program can check fields, quotations, citation provenance, score ranges and
some contradictions. It cannot prove that a model's meaning connection, humor
explanation or age estimate is correct merely because the response passes those
checks. Those remain model judgments that may need review. This design review
reduces avoidable sources of fabricated output; it does not certify zero hallucinations.

Production Python syntax, changed-module imports, frontend JavaScript syntax and
`git diff --check` passed. No new model calls, benchmark inference or unit-test
runs were performed. Previously reported scores belong to their saved source/prompt versions;
the prompt wording changes here have no newly measured performance claim.

The subsequent [system design review](system_design_review.md) checks for excessive
restrictions as well as unsupported acceptance. It updates L5/L6 response contract
to version 5 and adds offline regressions for the current end-to-end paths.
