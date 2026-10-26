"""Offline recall comparison against saved pre-change finder outputs.

This measures retrieval only; it never calls a model or changes a setting.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from crack.config import DEFAULT_SETTINGS, Settings
from crack.l0_scope import preprocess_input
from crack.l1_surface import analyze
from crack.l3_soundalikes import find_soundalikes

ROOT = Path(__file__).resolve().parents[1]


def summarize(rows: list[dict]) -> dict:
    positives = [r for r in rows if not r["negative"] and r["mechanism"] != "resegmentation"]
    negatives = [r for r in rows if r["negative"]]

    def target_supplied(row):
        return any(a["form"].casefold() == row["target"].casefold()
                   for c in row["candidates"] for a in c["alternates"])

    def located(row):
        return any(c["surface"].casefold() == row["pun_word"].casefold() for c in row["candidates"])

    return {
        "eligible_positives": len(positives),
        "target_supplied": sum(target_supplied(r) for r in positives),
        "target_supplied_ids": [r["id"] for r in positives if target_supplied(r)],
        "pun_word_flagged": sum(located(r) for r in positives),
        "negatives": len(negatives),
        "negative_finder_fires": sum(bool(r["candidates"]) for r in negatives),
    }


def compare(before_path: Path, items_path: Path, output: Path) -> dict:
    before = json.loads(before_path.read_text(encoding="utf-8"))
    inputs = [json.loads(line) for line in items_path.read_text(encoding="utf-8").splitlines() if line]
    if {r["id"] for r in before} != {r["id"] for r in inputs}:
        raise ValueError("Baseline and current corpus IDs differ")
    after = []
    for row in inputs:
        text = preprocess_input(row["text"])
        cands = find_soundalikes(analyze(text), text, DEFAULT_SETTINGS)
        after.append({"id": row["id"], "negative": bool(row["neg_type"]),
                      "mechanism": row["mechanism"], "target": row["target_word"],
                      "pun_word": row["pun_word"], "candidates": [c.model_dump() for c in cands]})
    output.mkdir(parents=True, exist_ok=True)
    (output / "finder_after.json").write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")
    excluded = {n for n in Settings.model_fields if n.endswith(("_API_KEY", "_BASE_URL"))}
    report = {
        "scope": "Local finder only, all existing candidate caps and thresholds unchanged; no model calls.",
        "baseline_sha256": hashlib.sha256(before_path.read_bytes()).hexdigest(),
        "corpus_sha256": hashlib.sha256(items_path.read_bytes()).hexdigest(),
        "config": DEFAULT_SETTINGS.model_dump(mode="json", exclude=excluded),
        "before": summarize(before), "after": summarize(after),
    }
    (output / "finder_comparison.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--items", type=Path, default=ROOT / "corpus/soundalike_items.jsonl")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare(args.before, args.items, args.output)
    print(json.dumps({k: report[k] for k in ("scope", "before", "after")}, indent=2))


if __name__ == "__main__":
    main()
