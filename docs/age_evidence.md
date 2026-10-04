# Age comprehension and appropriateness

Age assessment uses the existing L6 model request. L7 and L8 make no model
requests, and malformed or uncertain age results never trigger correction.
The web interface requests only the selected age; corpus runs use their
explicit requested age list.

## Evidence and compact estimate

L6 receives the actual text, anchored readings and a compact table of local
word-level AoA ratings. The table covers content vocabulary across the text
and the target/split parts. Missing ratings remain null. Local citations carry
the lookup method, source and resource hash; the model does not copy or invent
numeric citations.

The CSV records Kuperman word-level ratings. These are not acquisition ages
of individual senses or measured child understanding. Contextual model estimates
remain estimates. Numeric sense ages, a default AoA of five, a secondary-sense
plus-two adjustment and fixed genre age floors are not used. Historical fields
remain readable and are null in new records.

For each requested age, L6 returns exactly these fields:

| Field | Values |
|---|---|
| understanding | LIKELY / UNLIKELY / UNKNOWN |
| barrier | vocabulary / sense_a / sense_b / wordplay / background_knowledge for UNLIKELY; otherwise null |
| content_appropriate | true / false / null |
| inference_appropriate | true / false / null |
| reason | One short, nonempty sentence grounded in the text and readings |
| content_quote | Exact source quote for a content rejection; otherwise empty |
| prerequisite | Named concept for an inference rejection; otherwise empty |

Whole-text vocabulary, both readings, wordplay and necessary background
knowledge inform the understanding estimate. Missing ratings alone do not
establish difficulty. Inadequate evidence remains UNKNOWN/null. A topic word
alone does not establish inappropriate content.

## Local validation and stopping

L7 checks exact requested age keys, required fields, strict types and a
consistent named barrier. LIKELY gives FULLY_COMPREHENSIBLE; UNKNOWN gives
AOA_UNKNOWN. UNLIKELY records the estimated barrier and its reason. A sense B
knowledge barrier maps to SENSE_B_TOO_ADVANCED; wider vocabulary or a sense A
barrier maps to PARTIALLY_COMPREHENSIBLE. Knowing a surface word does not prove
familiarity with its particular figurative, idiomatic or specialist meaning. No detailed prerequisites are fabricated from an
unknown overall judgment.

L8 processes ages that passed L7. Other ages have unknown appropriateness.
Content rejection requires an exact source quote; inference rejection requires
a named prerequisite. Missing axes stay null. Empty concern strings never
become an automatic positive judgment.

Missing or malformed cached age data fails the age stage without another
request. AoA preparation failure requests detection only from L6 and records
an age error. Age failures preserve completed detection and leave unknown age
outputs. They cannot turn a non-pun into a pun or a failed run into a safety pass.

Current age response contract: `3`; aggregation version: `4`. Resume requires
both. Standalone age provider settings and legacy prompt files are compatibility
artifacts; runtime instructions live in `age_evidence.compact_age_prompt`.

## Evaluation

Two fresh October 4 corpus passes report gold-pun age agreement of 46/75 and
48/75, each with 67/75 assessed labels. Agreement among those assessed labels
is 68.7% and 71.6%. These are project-annotation agreement figures, not measured
child comprehension. See [the complete comparison](corpus_recovery_20261004.md).
Offline regressions verify no additional calls, exact age selection, unknown
preservation and failure isolation. Trace timing is reported separately from
the call budget; the compact task adds tokens to L6.

The [earlier two-call comparison](age_evidence_comparison.md) and
[five-dimension aggregation comparison](age_aggregation_comparison.md) describe
retired implementations. Their saved results retain their original definitions.
Use their frozen source snapshots to reproduce those experiments.
