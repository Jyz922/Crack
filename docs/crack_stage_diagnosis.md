# CRACK stage diagnosis — 2 October 2026

## Recommended priorities

Keep the executable evidence checks, explicit undecided/error outcomes, lexical
and AoA resources, and recorded traces. The strongest changes are **candidate
search orchestration** and **the age assessment algorithm**. Preserve contextual
logic and sense checks, but revise their application before making them optional.

| Component | Recommendation | Reason / proposed change |
|---|---|---|
| Input handling, response contracts, outcome states | Keep | Required fields, exact source quotations, source-table matches, and status consistency are checkable. Preserve retry/review and separate execution failure from uncertainty. |
| L1: surface structure and genre | Keep as metadata; revise routing | A question can itself contain wordplay. Its initial wh-word does not establish that a separate answer is required. |
| L2: WordNet and AoA lookup | Keep as supporting resources | Fast and auditable. Dictionary senses are proposals, not proof of contextual ambiguity. Preserve missing-data states and resource citations. |
| L3: candidate ranking | Revise priority; keep the candidate tail | WordNet category contrast and frequency balance do not identify the central wordplay in a sentence. Prioritize contextual targets; include phrases and legitimate splits. Handle empty sense groups explicitly. |
| L4: two readings and textual grounding | Keep the task and exact-quote checks; revise the call/search strategy | Most observed API cost comes from sequential per-term requests. Validate proposed targets in the complete text, and continue to alternatives if a candidate fails later checks. |
| L5: contextual resolution | Keep logic checks; revise applicability and scoring | The current genre template can require absent answers and treats causal/agent constraints as universally applicable. Weighted model scores can compensate for an essential logical failure. |
| L6: distinctness and rewrite check | Keep the checks; revise the acceptance rule and candidate handling | Different interpretations need not contradict one another. A rejected candidate should lead to another candidate assessment. Check that the selected contrast actually explains the identified wordplay. |
| L7: comprehension and vocabulary | Replace the current age heuristic; retain sourced lookup | Minimum AoA of words in a generated gloss and a fixed secondary-sense offset do not measure sense acquisition. Consider required vocabulary, idioms, both readings and background knowledge. |
| L8: content appropriateness | Replace keyword-only final verdicts; retain two separate axes | A keyword hit needs contextual interpretation. An empty keyword list does not establish appropriateness. Explain comprehension requirements separately from content concerns. |

### 1. Candidate search: fix the stop condition first

[`anchor_l4`](../src/crack/l4_anchoring.py) stops at the first candidate with two
accepted readings. L5/L6 then examine that candidate. Their rejection currently
ends the item, although other candidates can remain untested. The finalizer
recognizes incomplete search after an L4 negative, but does not apply the same
principle after L5/L6 reject the selected candidate.

In the saved SemEval run, **119 gold-positive texts** passed L4 and were then
rejected or left undecided by later checks. **114 still had untested candidates**;
in **66**, the exact normalized gold target was retrieved but never examined.
Gold-target matching here is case/space normalization only, without morphology
or alternative-target adjudication. Whether further search recovers these items
requires a rerun with the complete acceptance checks.

Examples from the unchanged SemEval gold:

| Item | Text / selected candidate | What the saved later check says | Next candidate opportunity |
|---|---|---|---|
| `hom_112` | “A thief who stole a calendar got twelve months.” Selected `calendar`. | L6 says the physical calendar and timekeeping system are related, and explicitly mentions the prison-sentence joke. | Gold target `got` is retrieved and untested; `months` is also available. |
| `hom_300` | “A gambling gardener usually hedges his bets.” Selected `gambling`. | L6 correctly notices that gambling for money and taking risks overlap. | Gold target `hedges` is retrieved and untested. |
| `hom_396` | “An undertaker can be one of your best friends, he is always the last one to let you down.” Selected `undertaker`. | L6 explicitly locates the contrast in “let you down”, rather than the two proposed undertaker roles. | Gold target `let` is retrieved and untested. |

The subsequent-check rejection is useful in these examples. Its scope should be
the **candidate**, followed by further search within a fixed operational budget.
A candidate can be accepted as the text's target only after its required checks
are complete. If alternatives remain unassessed when the budget expires, report
insufficient evidence. Distinguish a malformed/unavailable model response from
a semantic rejection; a failed call should remain visible.

This may increase calls for difficult texts. A contextual shortlist or a joint
proposal request should be evaluated alongside search continuation, with a
global item budget and complete per-candidate records. A shortlist must not
silently convert unexamined candidates into a confident negative.

### 2. L4: speed and implicit contextual evidence

The full-assignment run used **398 observed SDK calls** for 60 CRACK items:

| Stage | Calls | Input + output tokens | Share of tokens | Summed stage seconds |
|---|---:|---:|---:|---:|
| L4 | 342 | 643,377 | 90.17% | 1,841.11 |
| L5 | 29 | 32,228 | 4.52% | 128.23 |
| L6 | 27 | 37,938 | 5.32% | 145.03 |

L1–L3 together took approximately **1.20 summed seconds** in this resource-loaded
run. Stage seconds are summed over concurrent items, not batch wall times. The
complete CRACK batch took 278.42 seconds; the direct full-task batch took 136.70.
SDK-call counts are observed calls in the wrapper, not a claim about every
internal HTTP retry.

Each recorded L4–L6 request has one message. Maximum recorded prompt usage was
3,155 tokens for L4, 832 for L5 and 974 for L6; all 398 responses ended with
`stop`. This run shows repeated independent inference cost, with no recorded
truncation or growing conversation history. These observations do not prove
perfect instruction following.

On corpus item `J22` (“The teacher said it was the annual sports day. I asked if
I can skip.”), `skip` was retrieved and examined. L4 considered the movement
sense but rejected the sports-day cue as insufficient. Increasing the candidate
budget would not address that decision. The appropriate review is whether the
context conventionally evokes both readings, with human adjudication of weak
examples. Keep exact quotation checks; a contextual implication can be
explained using an exact quotation without inventing an event in the text.

### 3. L5: apply checks to the actual mechanism

On `J24` (“How many stories were in the library building?”), L4 found narratives
and building floors, grounded in `library` and `building`. L5 abstained because
the question has no separate answer and all QA dimensions cannot be assessed.
This exposes a template applicability issue: the task accepts sentences and
paragraphs containing homographic wordplay, including self-contained questions.

Retain the assignment's causal/negation requirement when the proposed joke
depends on a why/because relation. For other mechanisms, distinguish applicable,
failed and unassessed checks explicitly. Use constraints essential to that
mechanism rather than a universally required question-answer schema. Assessing
all five dimensions is not necessary for every form of wordplay.

The QA rule currently gives polarity/contrast 45% of the weighted score, with
15% for causality and 10% for agent identity. `D03` passed with agent 0.10 and
causal 0.55; `D24` passed with causal 0.20. Those subscores do not themselves prove
the labels are wrong: some jokes do not require the same agent or a causal chain.
They show why a scalar average cannot establish every essential condition.
Freeze current thresholds for the first orchestration comparison; do not select
new floors using these two items.

### 4. L6: distinguish meanings and identify the central contrast

On the project corpus, L6 successfully converted `D01` from a candidate-level
positive to a negative: muscle tissue and fighting strength describe overlapping
facets of the same literal explanation. It also stopped `D17`'s arbitrary
`post + al` analysis, because word parts do not form a coherent second meaning.
`D17` remains unresolved, rather than receiving a correct negative decision.

The current prompt and executable contract require both material difference and
mutual suppression. Revise that requirement in a separate variant: distinguish
two contextual interpretations without universally demanding that their
real-world situations contradict each other. Continue rejecting synonymy,
degree differences and unsupported split readings. In the assignment's skeleton
example, absence of internal organs and lack of courage can both be true; the
required contrast is between the contextual meanings of `guts`.

The saved SemEval item `hom_526` makes this issue concrete: “The frog went
unnoticed in the milkshake because it blended so well.” CRACK selected the gold
target `blended`. L6 recognized physical mixing and visual camouflage as
materially different, and said that replacing the target with “matched its
surroundings” removes the mixing reading. It nevertheless rejected distinctness
because both descriptions could be true of the frog. This is evidence for
revising the mutual-suppression requirement while preserving the other checks.

Also require an explicit connection between the selected contrast and the humor
being explained. On `J17`, the selected term is `overflowing`, and L6 acknowledges
that the alphabet/letter joke remains after its replacement. Removing an
incidental metaphor is not enough to demonstrate that the target explains the
main wordplay. Alternative targets should be adjudicated on their evidence;
exact disagreement with a gold target is not automatically an error.

The current “ambiguity ablation” is a model's explanation of a controlled
rewrite. It is not an independently executed original-versus-rewrite experiment.
Preserve the replacement and rationale for review. Evaluate selective independent
review or combining checks only after measuring their effects on full-task
outputs, rather than treating all self-ratings as verified evidence.

### 5. L7/L8: age reasoning needs an algorithmic change

The active [`run_l7` and `run_l8`](../src/crack/layers.py) call deterministic
heuristics without an LLM client. Editing their prompt files alone would not
change the current runner's age results.

The current L7 heuristic:

- takes the **minimum** known AoA among content words in a generated sense gloss;
- can lower Sense A's value below the target word's AoA;
- substitutes age 5 when Sense A data is absent, and can set Sense B to A + 2;
- drops missing compound-part values when taking a maximum;
- makes its `AOA_UNKNOWN` condition unreachable after the default value;
- checks mainly Sense B and a genre floor, rather than all required vocabulary
  and both meanings.

Changing `min` to `max` would still confuse gloss vocabulary with sense
acquisition. Preserve the actual word-level source rows and missing values.
Separately list necessary input vocabulary, idioms, split parts, contextual
knowledge and both readings. Age reasoning should cite the available data and
state which requirements are inferred or unknown. Avoid presenting default ages
or fixed offsets as sourced measurements.

L8 scans the original text and generated definitions for keywords, applies fixed
age cutoffs, and otherwise maps L7's result to an appropriateness verdict. Keep
keyword matches as inspectable screening evidence; assess the actual context
before issuing a final verdict. Comprehension and content suitability require
separate explanations. An absence of keyword hits is incomplete evidence.

On the **same 22 correctly detected puns**, current CRACK matched 47/66 project
age labels (71.21%), compared with direct's 53/66 (80.30%). This measures agreement
with the project's annotations, not observed child comprehension. The stronger
reason for revision is the unsupported algorithmic mapping above, rather than
optimizing toward those labels. Independent human review of age evidence is
pending.

## Recorded gate replay

The following rows replay accepted findings from the **same saved records**.
L4-prefix accepts a scoped, validated L4 pass; L4+L5 additionally requires the
recorded resolution pass. Full detection uses the saved final verdict. No new
calls, prompt edits, gold edits or threshold changes were made. Unresolved
gold-positive items remain misses for full-gold F1.

| Cohort / accepted checks | Accuracy, all | F1, full gold | Coverage | Original + rewrite both correct |
|---|---:|---:|---:|---:|
| Project 60: L4 prefix | 90.00% | 88.89% | 100.00% | 19/25 |
| Project 60: L4 + L5 prefix | 90.00% | 88.46% | 98.33% | 20/25 |
| Project 60: full detection | 91.67% | 92.00% | 96.67% | 21/25 |
| SemEval 2,250: L4 prefix | 84.58% | 89.93% | 99.16% | — |
| SemEval 2,250: L4 + L5 prefix | 83.11% | 88.78% | 99.16% | — |
| SemEval 2,250: full detection | 81.33% | 87.27% | 97.56% | — |

| Gate / cohort | False PUN → correct negative | False PUN → unresolved | True PUN → negative | True PUN → unresolved |
|---|---:|---:|---:|---:|
| L5, project 60 | 1 | 0 | 0 | 1 |
| L6/final, project 60 | 1 | 1 | 0 | 0 |
| L5, SemEval | 7 | 0 | 40 | 0 |
| L6/final, SemEval | 39 | 6 | 49 | 30 |

The checks improve project-corpus F1 and paired success, while reducing SemEval
recall and F1. This does not justify deleting L5/L6: a number of the rejected
SemEval candidates are weak or incidental analyses of genuinely positive texts.
Accepting those candidates may improve a binary score while retaining an
incorrect target or explanation. Fix search continuation, then compare the
check variants on complete outputs.

Of the 99 gold-positive texts that L4 completed as one-sense-only, the exact
normalized gold target was retrieved and tested in 79. The remaining 20 lacked
an exact target match among retrieved candidates; morphology or valid phrase
alternatives can affect this count. Candidate coverage and contextual rejection
are separate issues; more budget does not recover an already rejected reading.

All **29 recorded source-file hashes** match between these two cohorts. Effective
settings match after normalizing list order and explicit model overrides versus
provider defaults. Different datasets, collection times and task adapters remain
separate. Prefix replay is not a randomized causal ablation and supplies no
missing explanations or age results. Removing L5 while retaining L6 cannot be
measured for L5-rejected items without new L6 inference.

## Next controlled comparisons

1. **Candidate continuation only:** keep current prompts, semantic rules,
   thresholds, gold and source checks. Continue after a candidate-level L5/L6
   rejection, with a fixed item budget and explicit incomplete-search status.
2. **Contextual candidate proposals:** change L3/L4 proposal and call scheduling
   separately. Keep the same downstream checks. Measure targets, meanings,
   explanations, costs and coverage, including negative texts.
3. **Mechanism-specific L5 and revised L6:** isolate each change; do not lower
   all thresholds together. Evaluate coherence, material difference and the
   target's role in the humor through anonymous review.
4. **Sourced age algorithm:** hold detected target/readings fixed when comparing
   age implementations, so changes in detection coverage do not masquerade as
   better age reasoning.

These variants should be specified before their runs. Use a separately fixed
development set for choosing rules; the existing 60 items and SemEval are now
diagnostic/evaluation data that have been inspected. Keep their gold unchanged,
record suspected annotation problems separately, and confirm the selected design
on new held-out jokes, paired controls and ordinary texts. Repeat the frozen
final comparison with common resources and validation, and human review of
anonymous explanations. Do not choose the best stochastic run as the score.

`D03` and `D24` deserve annotation review: their rewritten text still evokes
two meanings. Their current gold labels remain untouched in every metric above.
An annotation review should record whether a rewrite actually removed the
required ambiguity and contextual logic, independently of a model's prediction.

## Artifacts

- [Stage counts, case IDs, timings and input hashes](crack_stage_diagnosis_20261002.json)
- [Offline diagnosis script](../scripts/diagnose_crack_stages.py)
- [Full assignment comparison](full_assignment_comparison.md)
- [Direct binary detection comparison](direct_detection_comparison.md)

Recompute the diagnosis from the preserved local records:

```bash
.venv/bin/python scripts/diagnose_crack_stages.py
```

The script performs offline record analysis only. The new files in this diagnosis
are the script, this report and its JSON summary. Production behavior is unchanged.
