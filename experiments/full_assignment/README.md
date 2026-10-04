# Full-assignment comparison

Compare the current CRACK configuration and a stateless direct LLM on the same
project corpus, including explanations and age assessments.

```bash
.venv/bin/python scripts/compare_full_assignment.py \
  --model gpt-6-luna --concurrency 8 --with-judge
```

This makes fresh API calls for both solutions and 120 anonymous reviewer calls
(60 cases, both A/B orders). Omit `--with-judge` to generate human-review packets
without automated reviews. The original corpus, production prompts and thresholds
are not modified.

Each timestamped directory under `runs/full_assignment_comparison/` contains the
frozen inputs, source and resources, raw responses, usage/timing, common validation,
metrics and review materials. Run the frozen scorer again without API calls:

```bash
.venv/bin/python runs/full_assignment_comparison/<timestamp>/runner.py \
  --run runs/full_assignment_comparison/<timestamp> --worker score
```

For independent human review, read `blind_review/rubric.md`, open
`blind_review/packets.html`, and fill `blind_review/human_ratings.csv` **before**
opening `blind_review/identity_key.json` or the result summary. Do not treat LLM
reviewer scores as completed human review or empirical child-age norms.

The fixed design and metric definitions are in [protocol.md](protocol.md).
