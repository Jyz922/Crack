# Fixed prompt development examples, v1

This set contains ten project-authored examples for inspecting prompt behavior:
four intended wordplay cases, four literal controls, one unresolved fragment and
one mechanism outside CRACK's supported scope. Expected findings are project
development annotations, with the proposed readings and rationale recorded in
each item. They may identify behavior that the current pipeline has not achieved.

All related cases share a `family_id` and belong to this development set. This
set is separate from the 60-item project evaluation corpus and the SemEval
corpora. Its examples and answers are not loaded into production prompts or
counted as independent benchmark results.

`examples.jsonl` is frozen by the SHA-256 in `manifest.json`. Publish a new version
directory for text or annotation changes, retaining this version for comparison.
Use the same fixed examples when inspecting alternative prompt drafts; do not
replace failures with easier examples or tune against held-out evaluation labels.

`blind.jsonl` contains only IDs, text and an empty target-age list.
`expected.jsonl` maps the development expectations into the existing evaluation
schema. Both derived files have their own hashes in the manifest. No age labels
are supplied. To inspect a prompt draft on this fixed development set:

```bash
crack --input corpus/prompt_development/v1/blind.jsonl \
  --eval corpus/prompt_development/v1/expected.jsonl \
  --output runs/prompt_development_v1 --backend openai --concurrency 4
```

This command makes provider requests. Its results measure agreement with these
development annotations, rather than independent benchmark performance.

The overlap audit checks these texts against known evaluation inputs. Single
target-word overlap is a review hint, since a shared English word does not by
itself disclose a test answer. Close paraphrases and shared templates need manual
review beyond the automated phrase checks.
