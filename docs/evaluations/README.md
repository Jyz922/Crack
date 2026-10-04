# Published October 4 regression evidence

These three complete 60-item runs use the same project texts and gold labels.
The recovery and repeat runs also use the same detection/age implementation,
prompts, model and effective settings. No responses were selected between runs.

| Run | Exact labels | Binary detection | Gold-pun age labels |
|---|---:|---:|---:|
| [Before recovery](reliability_baseline_20261004/evaluation.json) | 47/60 | 49/60 | 37/75 |
| [Recovery](recovery_20261004/evaluation.json) | 55/60 | 56/60 | 46/75 |
| [Fresh user repeat](repeat_20261004/evaluation.json) | 55/60 | 56/60 | 48/75 |

Each directory contains `records.jsonl`, the unchanged original
`evaluation.json`, a sanitized `run_meta.json`, and `publication_manifest.json`.
The baseline's original summary predates `age_gold_puns`; its manifest records
the additional subset view computed from the same predictions and gold labels.

The per-item records are an explicitly declared projection: L2's dictionary
payload and raw L4/age attempt logs were omitted. L3 proposals, semantic
findings, exact anchors, age outputs, stage traces and final verdicts remain.
The metadata replaces the absolute local input path with the repository path.
Manifests retain original and published file hashes and list these changes.
Compact files support rescoring, not resume or reproduction of raw SDK events.

From the repository root, recompute and check every metric in each original
summary without network requests:

```bash
.venv/bin/python - <<'PY'
import hashlib
import json
from pathlib import Path
from crack.corpus import evaluate_run

for run in sorted(Path("docs/evaluations").iterdir()):
    if not run.is_dir():
        continue
    manifest = json.loads((run / "publication_manifest.json").read_text())
    for filename, key in [
        ("records.jsonl", "published_records_sha256"),
        ("evaluation.json", "published_evaluation_sha256"),
        ("run_meta.json", "published_run_meta_sha256"),
    ]:
        assert hashlib.sha256((run / filename).read_bytes()).hexdigest() == manifest[key]
    gold = Path(manifest["gold_path"])
    assert hashlib.sha256(gold.read_bytes()).hexdigest() == manifest["gold_sha256"]
    expected = json.loads((run / "evaluation.json").read_text())
    actual = evaluate_run(run / "records.jsonl", gold)
    assert all(actual[key] == value for key, value in expected.items())
    print(run.name, actual["correct_classification"], actual["binary_detection"]["correct"], actual["age_gold_puns"])
PY
```

These records establish saved-result arithmetic and local contract validity.
They are not signed provider receipts or proof of model semantic correctness.
The first recovery directory additionally publishes a compact SDK invocation
index with model, stage, duration and response metadata; SDK-internal HTTP
retries remain outside that index. The project corpus was inspected during
development and is a regression set, not an unseen benchmark. Its age labels
are curator judgments rather than observed child performance.

After the live repeats, the unused SemEval evaluator/report output removed
external system tables and comparison fields. Detection/age code and prompts
match the live-evaluated source; source hashes preserve the original snapshots.
The [full comparison](../corpus_recovery_20261004.md) records remaining errors,
prediction variation, call accounting and descriptive timing limits.
