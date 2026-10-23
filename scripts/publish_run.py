"""Publish a completed run under docs/evaluations/<name>/ as a compact, rescorable copy.

Follows the October 4 convention (docs/evaluations/README.md): records.jsonl
omits l2_result, l4_attempts and age_attempts; evaluation.json and
run_meta.json are copied unchanged (run_meta already stores repository-relative
paths and no secrets); publication_manifest.json records original and
published hashes and confirms an offline rescore reproduces every metric.

    py -3.11 scripts/publish_run.py runs/<timestamp> <name> <gold.jsonl> "<note>"
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

from crack.corpus import evaluate_run

ROOT = Path(__file__).resolve().parents[1]
OMIT = ("l2_result", "l4_attempts", "age_attempts")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(run_dir: str, name: str, gold: str, note: str) -> None:
    src, dst, gold_path = ROOT / run_dir, ROOT / "docs" / "evaluations" / name, ROOT / gold
    meta = json.loads((src / "run_meta.json").read_text(encoding="utf-8"))
    if any(marker in json.dumps(meta) for marker in ("sk-", "_API_KEY")):
        raise SystemExit("run_meta.json looks like it contains a secret; refusing to publish")
    dst.mkdir(parents=True, exist_ok=True)
    with (src / "records.jsonl").open(encoding="utf-8") as fin, (dst / "records.jsonl").open("w", encoding="utf-8") as fout:
        for line in fin:
            if line.strip():
                record = json.loads(line)
                for field in OMIT:
                    record.pop(field, None)
                fout.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    shutil.copyfile(src / "evaluation.json", dst / "evaluation.json")
    shutil.copyfile(src / "run_meta.json", dst / "run_meta.json")
    expected = json.loads((dst / "evaluation.json").read_text(encoding="utf-8"))
    actual = evaluate_run(dst / "records.jsonl", gold_path)
    matches = all(actual.get(k) == v for k, v in expected.items())
    manifest = {
        "original_run_directory": run_dir.replace("\\", "/"),
        "original_records_sha256": sha(src / "records.jsonl"),
        "original_run_meta_sha256": sha(src / "run_meta.json"),
        "original_evaluation_sha256": sha(src / "evaluation.json"),
        "published_records_sha256": sha(dst / "records.jsonl"),
        "published_run_meta_sha256": sha(dst / "run_meta.json"),
        "published_evaluation_sha256": sha(dst / "evaluation.json"),
        "omitted_record_fields": list(OMIT),
        "item_count": expected.get("total_items"),
        "gold_path": gold.replace("\\", "/"),
        "gold_sha256": sha(gold_path),
        "git_sha": meta.get("git_sha"),
        "offline_rescore_matches_every_original_metric": matches,
        "note": note,
        "limitations": [
            "Compact records are an explicitly declared projection, not raw SDK receipts.",
            "Local structural revalidation and metric arithmetic do not prove model semantic correctness.",
            "Single runs of a nondeterministic model; compare runs rather than reading one in isolation.",
        ],
    }
    (dst / "publication_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(name, "rescore matches:", matches)
    if not matches:
        raise SystemExit("offline rescore does not reproduce evaluation.json")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
