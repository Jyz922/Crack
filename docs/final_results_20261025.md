# Final full runs and separate anchor-repair follow-up

All three runs completed October 25 local time (October 26 UTC), using OpenAI
`gpt-6-luna`. The two full runs use contract 7; the two-item follow-up uses
contract 8. Original run outputs and evaluations are retained without merging
or replacing individual predictions. Prompt/source hashes and lexical resource
identities are preserved in their metadata.

| Metric | Final soundalike | Final regression | Separate repair |
|---|---:|---:|---:|
| Items | 79 | 60 | 2 |
| Exact classifications | 69/79 (87.3%) | 54/60 (90.0%) | 1/2 (50.0%) |
| Binary correct, all items | 71/79 (89.9%) | 54/60 (90.0%) | 2/2 (100.0%) |
| Explicit decisions | 78/79 | 59/60 | 2/2 |
| Execution failures | 1 | 1 | 0 |
| TP / FP / TN / FN | 33 / 5 / 38 / 2 | 22 / 3 / 32 / 2 | 2 / 0 / 0 / 0 |

Each full run has one additional unresolved positive, outside its TP/FN counts.
For regression age assessment, agreement across all 75 labels on reference puns
is 44/75 (58.7%), with 62/75 assessed and 44/62 agreement among assessed labels.
The 50/180 headline age figure includes literal controls that are generally not
age-assessed. Age labels are project annotations, not observed child outcomes.

The soundalike run fails T3 at L4 because its enclosing split quote does not
match the contract-7 exact-token requirement. The regression run fails J13
because the definition heading is used as one sound-substitution anchor.
The generalized contract-8 changes and all-139-reply offline replay are described
in [the anchor admissibility report](anchor_contract_v8_20261025.md).

In the separate real follow-up, both items complete with positive decisions:

- T3 uses the supplied `cat` + `nap` resegmentation; an enclosing verbatim quote
  is deterministically narrowed to the source token. Its mechanism label matches.
- J13 uses `mushroom` / `much room` sound substitution with a definition-heading
  anchor and separate body evidence. It remains a mechanism-label disagreement
  with the reference compound-split annotation, despite the correct binary
  decision. No label or semantic threshold was changed to remove that difference.

The follow-up assesses recovery of two known failures. It is neither an unseen
test nor a rerun of the complete corpora. Its 2/3 age agreement is descriptive
only. The full-run errors and denominators remain visible.

Published compact records, unchanged evaluations, metadata, manifests and full
L4 request/response audit projections are under
`docs/evaluations/final_soundalike_20261025/`,
`docs/evaluations/final_regression_20261025/` and
`docs/evaluations/anchor_contract_v8_live_20261025/`.
