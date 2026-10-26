# Prompt example separation audit

## Scope and result

The current prompt audit finds **0 phrase-overlap failures and 0 review hints**
across 6,766 corpus text rows and 26 subjects. Rows include repeated texts in
multiple exported files; this is not a count of independent examples. The
machine-readable evidence and SHA-256 hashes of audited subjects are in
[the audit report](evaluations/prompt_overlap_20261025.json).

Audited subjects include the eight production prompt Markdown files (the L7/L8
files are compatibility references), static instruction strings in
`compact_age_prompt`, `soundalike_note` and `_anchor_shortlist`, five experiment
prompt files, and ten frozen v1 development examples. Prompt instructions are
checked against all corpus JSONL rows containing `text`, including soundalike,
original regression, SemEval, development and confirmation inputs. The ten
development examples are separately checked against evaluation inputs; they
are not themselves inserted into production prompts.

No current corpus joke examples or labeled demonstrations were found in the
production instructions. No production prompt edits were needed. This patch
expands the audit and regression checks without changing inference prompts.

## Runtime input and answer separation

- The current item's text is necessarily provided as the input to classify.
  It is not a worked demonstration or the correct answer.
- L4 receives locally retrieved candidate forms, pronunciation similarities,
  and dictionary sense IDs/definitions. Dictionary example sentences stored in
  `SenseEntry.example` are not included in its prompt; a captured-request test
  checks this boundary.
- L5 and L6 receive the current item's upstream proposed readings and source
  quotes. These are model hypotheses validated by local code, not corpus gold.
- The age appendix supplies requested ages and retrieved word-level AoA values,
  not corpus age verdicts or curator explanations.
- `load_blind` rejects extra fields; CLI evaluation loads the gold file only
  after inference. The production inference modules do not load development
  demonstrations or gold labels into requests.

## Guard and limits

The audit normalizes case and punctuation. An entire matching corpus input of
at least three tokens fails; any shared eight-token span fails; six/seven-token
spans and quoted target terms are surfaced for review. Tests also check
short examples, development files without `blind` in their names, and Python
f-string instruction literals. A shared single word is not by itself a leaked
example. Run offline with:

```bash
.venv/bin/python scripts/audit_prompt_overlap.py --output docs/evaluations/prompt_overlap_20261025.json
```

This is a check for direct/example phrase overlap, not proof against semantic
paraphrases or every future code path. It cannot determine whether the hosted
model saw public jokes during pretraining. There is no project parameter
training in this inference pipeline. Prior inspection of benchmark errors also
means these familiar corpora should be described as regression/evaluation sets,
not a fresh untouched final test. To estimate generalization after further
prompt development, freeze the prompt and evaluate a new independent held-out
set once; keep any label review separate from changing prompts on that set.
