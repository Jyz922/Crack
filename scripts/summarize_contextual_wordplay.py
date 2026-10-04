#!/usr/bin/env python3
"""Summarize frozen contextual-prompt results and both anonymous review orders."""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import statistics


def summarize(run):
    spec = importlib.util.spec_from_file_location("frozen_support", run / "comparison_support.py")
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    manifest = support.check_frozen(run)
    stage = json.loads((run / "stage_evaluation.json").read_text())
    course = json.loads((run / "evaluation.json").read_text())
    directory = run / "blind_review"
    packets = support.rows(directory / "packets.jsonl")
    review_manifest = json.loads((directory / "manifest.json").read_text())
    if support.sha(directory / "packets.jsonl") != review_manifest["packets_sha256"]:
        raise ValueError("Anonymous packets changed")
    if support.sha(directory / "identity_key.json") != review_manifest["identity_key_sha256"]:
        raise ValueError("Identity key changed")
    keys = {r["case"]: r for r in json.loads((directory / "identity_key.json").read_text())}
    cases = {p["case"] for p in packets}
    reviews = support.rows(directory / "llm_reviews.jsonl")
    if len({(r["case"], r["swapped"]) for r in reviews}) != len(reviews):
        raise ValueError("Duplicate review order")
    if any(r["case"] not in cases for r in reviews):
        raise ValueError("Review outside fixed changed-output subset")
    preferences = {}
    scores = {a: {d: [] for d in support.DIMENSIONS} for a in manifest["arm_order"]}
    errors = {a: Counter() for a in scores}
    for row in reviews:
        review = row["review"]
        if review is None:
            continue
        support.judge_validate(review)
        key = keys[row["case"]]
        for label in ("A", "B"):
            original_label = ("B" if label == "A" else "A") if row["swapped"] else label
            arm = key[original_label]
            for dimension, value in review[label]["scores"].items():
                if value is not None:
                    scores[arm][dimension].append(value)
            errors[arm].update(e["type"] for e in review[label]["errors"])
        preference = review["preference"]
        if preference != "TIE":
            original_label = ("B" if preference == "A" else "A") if row["swapped"] else preference
            preference = key[original_label]
        preferences.setdefault(row["case"], {})[row["swapped"]] = preference
    stable = Counter()
    for case in cases:
        orders = preferences.get(case, {})
        stable[(orders[False] if orders[False] == orders[True] else "ORDER_UNSTABLE")
               if set(orders) == {False, True} else "INCOMPLETE"] += 1
    review_summary = {
        "reviewer_model": manifest["model"], "case_count": len(cases),
        "selection": review_manifest["selection"], "planned_requests": 2 * len(cases),
        "completed_requests": sum(r["review"] is not None for r in reviews),
        "stable_case_preferences": dict(stable),
        "mean_scores": {a: {d: {"mean": statistics.mean(v) if v else None, "judgments": len(v)}
                            for d, v in dims.items()} for a, dims in scores.items()},
        "reviewer_error_flags": {a: dict(v) for a, v in errors.items()},
        "api_usage": support.api_totals(reviews),
        "human_review": "pending; automated judgments do not adjudicate gold or child comprehension",
    }
    a, b = course["arms"]["baseline"], course["arms"]["contextual"]
    checks = {
        "no_new_contract_failures": b["common_contract_failures"] == 0,
        "development_positive_passes_preserved": stage["contextual"]["development"]["counts"].get("tp", 0) >= stage["baseline"]["development"]["counts"].get("tp", 0),
        "confirmation_positive_passes_preserved": stage["contextual"]["confirmation"]["counts"].get("tp", 0) >= stage["baseline"]["confirmation"]["counts"].get("tp", 0),
        "negative_false_passes_not_increased": all(stage["contextual"][s]["counts"].get("fp", 0) <= stage["baseline"][s]["counts"].get("fp", 0) for s in ("development", "confirmation")),
        "negative_false_passes_reduced": any(stage["contextual"][s]["counts"].get("fp", 0) < stage["baseline"][s]["counts"].get("fp", 0) for s in ("development", "confirmation")),
        "course_accuracy_preserved": b["correct"] >= 55,
        "course_f1_preserved": b["f1_full_gold"] >= a["f1_full_gold"],
        "course_pairs_preserved": b["pair_success_count"] >= 21,
        "course_coverage_at_least_58_of_60": b["coverage"] >= 58/60,
        "stage_no_execution_errors": all(stage[arm][s]["counts"].get("execution_failed", 0) == 0 for arm in stage for s in ("development", "confirmation")),
    }
    result = {"run_path": str(run), "model": manifest["model"], "stage": stage, "course": course,
              "llm_changed_output_review": review_summary, "adoption_checks": checks,
              "passes_numeric_acceptance": all(checks.values()),
              "production_action": "Retain baseline; contextual draft fails frozen numeric acceptance" if not all(checks.values()) else "Requires review of contextual regressions before adoption",
              "manifest_sha256": support.sha(run / "manifest.json"),
              "summary_script_sha256": support.sha(Path(__file__)),
              "artifact_sha256": {p.relative_to(run).as_posix(): support.sha(p) for p in [run / "stage_evaluation.json", run / "evaluation.json", run / "changes.jsonl", directory / "llm_reviews.jsonl", directory / "packets.jsonl"]}}
    support.write(run / "summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.run.resolve())
    print(json.dumps({"adoption_checks": result["adoption_checks"], "production_action": result["production_action"],
                      "review_preferences": result["llm_changed_output_review"]["stable_case_preferences"]}, indent=2))


if __name__ == "__main__":
    main()
