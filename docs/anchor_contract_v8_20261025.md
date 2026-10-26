# Contract 8: structural anchor admissibility

## Design basis

An anchor identifies a position in the source; its admissibility must be
separate from whether the proposed meaning or joke is correct. Two restrictions
in contract 7 confused an admissible source position with a required quotation
format. Contract 8 corrects those restrictions without changing prompts,
retrieval, resource snapshots, models, thresholds, or semantic verdicts.

The rules have no item IDs, dataset paths, target words or vocabulary allowlist
in production code. Twenty-three independent constructed test cases exercise
acceptance, rejection and raw-response preservation. Benchmark replies are used
only afterward for a declared regression replay, not as prompt demonstrations.

## Rule 1: a split's source token can be located inside its quotation

Resegmentation concerns the internal spelling of a selected token. A model
quoting a larger source phrase containing that token has still supplied its
location. The locally accepted anchor may therefore be narrowed when:

- The raw quote is a verbatim nonblank substring of the input, as before.
- The target is a detected split candidate and the proposed parts exactly
  match a supplied segmentation, as before.
- The enclosing quote occurs exactly once and the full target has exactly one
  token-bounded occurrence in the text. Letters, digits, underscores, apostrophes
  and hyphens cannot be mistaken for an external token boundary.
- The target occurrence lies completely inside the quoted source span.

The accepted quote is copied from that exact source span. Case, spelling and
punctuation are not guessed or repaired. Original exact-target anchors retain
their previous behavior. Ambiguous repetitions, missing targets, partial-word
matches and invented/nonverbatim quotations are rejected. The source text is
still passed downstream in full; narrowing does not certify the interpretation
of surrounding modifiers, negation or the sentence as a whole.

## Rule 2: definition headings are evidence positions

In a lexical `headword: definition` construction, the heading introduces the
lexical form whose conventional meaning is being contrasted with the body.
Requiring both anchors to exclude the headword makes that construction
unrepresentable even when its body has a separate contextual cue.

One target-only quote is admissible when the existing L1 router identifies a
definition-style input, the target is exactly its initial colon-delimited
heading, and the other quote uniquely occurs entirely in the body. Both anchors
cannot be target-only; a quote spanning the whole heading and body does not
count as the independent body anchor. Other existing checks remain active.

This structural rule applies to ordinary separate-context homographs as well as
sound substitutions/pairs. It does not permit a target-only anchor in arbitrary
sentences or speaker-mismatch claims. It does not assert that a headword
establishes the model's specific meaning, or that its relationship to the body
is humorous: L5 and L6 still assess those claims. Negative model statuses are
not promoted to PASS. A title/body explanation can still be semantically wrong.

## Audit and versioning

`L4Attempt.parsed_response` and raw provider text remain untouched.
`validated_response` records the accepted local result.
`anchor_adjustments` records the rule, field, raw and accepted quotes, zero-based
half-open source offsets, and reason. A heading event records an admissibility
exception even though no quotation changes. Events are committed only after
all response checks succeed. No corrective model call or retry is added.

`RESPONSE_CONTRACT_VERSION` is now 8, so old records cannot be resumed as if
they had passed the new contract. The prior frozen source and final run files
remain intact.

## Offline replay and its limits

Replay used all 139 saved parsed L4 replies from the final 79-item soundalike
and 60-item regression runs, with each run's own verification percentile and
supplied candidate data. The baseline is the frozen contract-7 source file,
whose SHA-256 is included in
[the replay evidence](evaluations/anchor_contract_v8_20261025/replay.json).

| Parsed reply outcome | Contract 7 | Contract 8 |
|---|---:|---:|
| Valid reply | 136 | 138 |
| Substantive phonetic rejection | 1 | 1 |
| Response-contract error | 2 | 0 |

The two newly valid replies are T3 (split-token narrowing) and J13 (definition
heading). Every one of the 136 previously valid reply outputs is unchanged;
the existing phonetic rejection is also unchanged. This is evidence about
response acceptance only. It is **not** a new detection accuracy result: those
two inputs still need L5/L6 processing, which may legitimately reject them.
The original evaluation files and their failure counts are not rewritten.

Full offline verification: **611 passed, 10 live tests deselected**; two
pre-existing FastAPI lifecycle deprecation warnings remain. Prompt overlap
audit: zero failures and zero review hints. All production prompt template
hashes and frozen retrieval/threshold source bytes are unchanged by this patch.

Reproduce the replay without API calls:

```bash
.venv/bin/python scripts/replay_l4_anchor_contract.py --baseline-validator docs/evaluations/exact_homophone_l4_20261025/after/validation.py --records runs/final_soundalike/20261026T023324Z/records.jsonl --records runs/final_regression/20261026T023549Z/records.jsonl --output docs/evaluations/anchor_contract_v8_20261025
```

The generated `newly_valid_blind.jsonl` is selected by validator outcome, not
hardcoded item IDs. A fresh two-item run is a follow-up repair experiment, not
a replacement for the complete original runs or an independently held-out test.
