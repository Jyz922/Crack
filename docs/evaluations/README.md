# Published evaluation evidence

## October 25: final runs and separate anchor repair

| Run | Exact labels | Binary detection | Coverage | Execution failures |
|---|---:|---:|---:|---:|
| [Final soundalike](final_soundalike_20261025/evaluation.json) | 69/79 | 71/79 | 78/79 | 1 |
| [Final regression](final_regression_20261025/evaluation.json) | 54/60 | 54/60 | 59/60 | 1 |
| [Separate two-item anchor repair](anchor_contract_v8_live_20261025/evaluation.json) | 1/2 | 2/2 | 2/2 | 0 |

The full runs retain their contract-7 predictions and failures. The contract-8
follow-up resolves both execution failures; one mechanism label still differs
from the authored reference. Do not combine these three runs into a new full-run
accuracy claim. See [the final report](../final_results_20261025.md).

Each of these directories also contains `l4_requests.jsonl`, preserving every
rendered L4 prompt, its hash, raw response text and local validation audit.
Its SHA-256 and projection fields are declared in the publication manifest.
Current rescoring reproduces detection and age metrics. For the older contract-7
runs only, `unverified_contract_items` now counts historical records, so that
provenance difference is recorded explicitly; original evaluations are unchanged.

## October 25: resource refresh user reruns

| Run | Exact labels | Binary detection | Coverage | Execution failures |
|---|---:|---:|---:|---:|
| [Soundalike](resource_refresh_soundalike_20261025/evaluation.json) | 67/79 | 71/79 | 79/79 | 0 |
| [Original corpus regression](resource_refresh_regression_20261025/evaluation.json) | 51/60 | 53/60 | 59/60 | 1 |

These runs use OEWN 2025 and the pinned official CMUdict snapshot. The working
tree was uncommitted, so the Git HEAD is the earlier base; `run_meta.json`
source hashes and resource checksums identify the actual implementation.
Directory timestamps are October 26 UTC, corresponding to October 25 local time.
Both compact copies rescore to every original metric. See the
[live comparison and error analysis](../resource_refresh_live_20261025.md).
The `resource_refresh_20261025` subdirectory contains offline local-comparison
analysis, rather than a published provider run.

## October 23: soundalike extension

| Run | Corpus | Exact labels | Binary detection | Code |
|---|---|---:|---:|---|
| [Soundalike, before fixes](soundalike_before_fixes_20261023/evaluation.json) | `corpus/soundalike_*` (79) | 61/79 | 62/79 | 7521c9e |
| [Soundalike, after fixes](soundalike_after_fixes_20261023/evaluation.json) | `corpus/soundalike_*` (79) | 71/79 | 73/79 | e856543 |
| [Homograph regression 1](regression_1_20261023/evaluation.json) | `corpus/joke_corpus_*` (60) | 52/60 | 54/60 | e856543 |
| [Homograph regression 2](regression_2_20261023/evaluation.json) | `corpus/joke_corpus_*` (60) | 54/60 | 54/60 | e856543 |

Published with `scripts/publish_run.py`, using the same projection and manifest
fields as below; every manifest records that an offline rescore reproduces the
original metrics. Soundalike labels are authored and not yet double-labelled.

## October 4 regression

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
    if not run.is_dir() or not (run / "publication_manifest.json").is_file():
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
    differences = {key for key, value in expected.items() if actual[key] != value}
    if differences:
        from crack.validation import RESPONSE_CONTRACT_VERSION
        metadata = json.loads((run / "run_meta.json").read_text())
        assert differences == {"unverified_contract_items"}
        assert metadata["validation_version"] != RESPONSE_CONTRACT_VERSION
    print(run.name, actual["correct_classification"], actual["binary_detection"]["correct"], actual["age_gold_puns"])
PY
```

These records establish saved-result arithmetic under their recorded contracts;
historical records are not claimed to have passed the current contract.
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
