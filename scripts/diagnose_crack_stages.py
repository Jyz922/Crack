#!/usr/bin/env python3
"""Audit saved stage decisions and costs without inference or changing gold.

Prefix replay means accepting the already recorded L4/L5 findings at that point.
It is not a rerun of an independently ablated system: downstream checks absent
from a record remain absent, and newly accepted puns have no fabricated analysis.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
POSITIVE = {"VALID_HOMOGRAPH_JOKE", "VALID_COMPOUND_SPLIT_JOKE"}
NEGATIVE = {"ONE_SENSE_ONLY", "NO_WORDPLAY", "FAILED_RESOLUTION"}
PREFIX_LAYERS = {"L0-pre", "L1", "L2", "L3", "L4"}
EXCLUDED_SCOPE = {"OUT_OF_SCOPE_HOMOPHONE", "OUT_OF_SCOPE_NONLEXICAL_JOKE"}


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metric(predictions, gold):
    counts = Counter()
    for item_id, positive in gold.items():
        label = predictions[item_id]
        if label not in {"PUN", "NON_PUN"}:
            counts["unresolved_positive" if positive else "unresolved_negative"] += 1
        elif label == "PUN":
            counts["tp" if positive else "fp"] += 1
        else:
            counts["fn_decided" if positive else "tn"] += 1
    tp, fp, tn, fn = (counts[k] for k in ("tp", "fp", "tn", "fn_decided"))
    up = counts["unresolved_positive"]
    ratio = lambda a, b: a / b if b else 0.0
    result = {**{k: counts[k] for k in (
        "tp", "fp", "tn", "fn_decided", "unresolved_positive", "unresolved_negative")},
        "items": len(gold), "correct": tp + tn,
        "accuracy_all": ratio(tp + tn, len(gold)),
        "precision": ratio(tp, tp + fp), "recall_full_gold": ratio(tp, tp + fn + up),
        "f1_full_gold": ratio(2 * tp, 2 * tp + fp + fn + up),
        "coverage": ratio(tp + fp + tn + fn, len(gold)),
        "outcomes": dict(Counter(predictions.values()))}
    pairs = [(i, "D" + i[1:]) for i in gold if i.startswith("J") and "D" + i[1:] in gold]
    if pairs:
        successes = sum(predictions[j] == "PUN" and predictions[d] == "NON_PUN" for j, d in pairs)
        result["paired_success"] = {"correct": successes, "pairs": len(pairs),
                                    "rate": successes / len(pairs)}
    return result


def prefix(record, include_l5):
    layers = PREFIX_LAYERS | ({"L5"} if include_l5 else set())
    if any(t["layer"] in layers and t["status"] in {"ERROR", "REJECTED"}
           for t in record["trace"]):
        return "EXECUTION_FAILED"
    l4 = record.get("l4_result") or {}
    status = l4.get("anchoring_status")
    if status not in {"PASS", "ONE_SENSE_ONLY"}:
        return "INSUFFICIENT_EVIDENCE"
    # Preserve the recorded scope rule in both prefix rows.
    if record["final"]["scope_label"] in EXCLUDED_SCOPE:
        return "OUT_OF_SCOPE"
    if status == "ONE_SENSE_ONLY":
        return ("INSUFFICIENT_EVIDENCE" if
                (record.get("l4_search") or {}).get("untested_terms", 0)
                else "NON_PUN")
    if not include_l5:
        return "PUN"
    status = (record.get("l5_result") or {}).get("resolution_status")
    if status == "RESOLUTION_PASS":
        return "PUN"
    if status == "RESOLUTION_FAIL":
        return "NON_PUN"
    if status in {"TRUNCATED_OUTPUT", "EXECUTION_FAILED"}:
        return "EXECUTION_FAILED"
    return "INSUFFICIENT_EVIDENCE"


def transition(before, after, gold):
    counts = Counter()
    changes = []
    for item_id, old in before.items():
        new = after[item_id]
        if old == new:
            continue
        expected = "PUN" if gold[item_id] else "NON_PUN"
        changes.append({"item_id": item_id, "gold": expected,
                        "before": old, "after": new})
        counts["positive_changed" if gold[item_id] else "negative_changed"] += 1
        if old == "PUN":
            if gold[item_id]:
                counts["true_positive_to_negative" if new == "NON_PUN"
                       else "true_positive_to_unresolved"] += 1
            else:
                counts["false_positive_to_true_negative" if new == "NON_PUN"
                       else "false_positive_to_unresolved"] += 1
    return {"counts": dict(counts), "changes": changes}


def audit(records_path, gold_path, wrappers=False):
    raw = read_rows(records_path)
    records = [r["native_record"] for r in raw] if wrappers else raw
    gold_rows = read_rows(gold_path)
    if any(g["gold_label"] not in POSITIVE | NEGATIVE for g in gold_rows):
        raise ValueError("Unsupported gold label")
    gold = {g["id"]: g["gold_label"] in POSITIVE for g in gold_rows}
    ids = [r["item_id"] for r in records]
    if len(set(ids)) != len(records) or set(ids) != set(gold):
        raise ValueError("Records must uniquely cover the frozen gold items")
    if wrappers and any(r["text"] != r["native_record"]["text"] for r in raw):
        raise ValueError("Wrapper/native text mismatch")
    predictions = {
        "L4_prefix": {r["item_id"]: prefix(r, False) for r in records},
        "L4_L5_prefix": {r["item_id"]: prefix(r, True) for r in records},
        "full_detection": {r["item_id"]: r["final"]["detection_status"] for r in records},
    }
    changes = {"L5": transition(predictions["L4_prefix"], predictions["L4_L5_prefix"], gold),
               "L6_and_final": transition(predictions["L4_L5_prefix"], predictions["full_detection"], gold)}
    remaining = Counter()
    remaining_by_gold = Counter()
    target_checks = Counter()
    gold_by_id = {g["id"]: g for g in gold_rows}
    normalize = lambda v: " ".join(v.strip().casefold().replace("_", " ").split())
    downstream = []
    for r in records:
        item_id = r["item_id"]
        l3 = r.get("l3_result") or {}
        search = r.get("l4_search") or {}
        target = normalize(gold_by_id[item_id].get("ambiguous_term", ""))
        retrieved = {normalize(c["term"]) for c in l3.get("candidates", []) + l3.get("deferred_candidates", [])}
        tested = {normalize(c["term"]) for c in search.get("findings", [])}
        if (gold[item_id] and (r.get("l4_result") or {}).get("anchoring_status") == "ONE_SENSE_ONLY"
                and predictions["full_detection"][item_id] == "NON_PUN"):
            target_checks["L4_negative_gold_positives"] += 1
            target_checks["L4_negative_gold_target_retrieved"] += int(bool(target) and target in retrieved)
            target_checks["L4_negative_gold_target_tested"] += int(bool(target) and target in tested)
        if predictions["L4_prefix"][item_id] != "PUN" or predictions["full_detection"][item_id] == "PUN":
            continue
        l4, l5, l6 = (r.get(k) or {} for k in ("l4_result", "l5_result", "l6_result"))
        stage = "L5" if l5.get("resolution_status") != "RESOLUTION_PASS" else "L6"
        untested = (r.get("l4_search") or {}).get("untested_terms", 0)
        remaining[f"{stage}_{'with' if untested else 'without'}_untested_candidates"] += 1
        remaining_by_gold[f"{stage}_{'positive' if gold[item_id] else 'negative'}_{'with' if untested else 'without'}_untested"] += 1
        if gold[item_id]:
            target_checks["downstream_rejected_gold_positives"] += 1
            target_checks["downstream_selected_target_exact_matches_gold"] += int(bool(target) and normalize(l4.get("target_term", "")) == target)
            target_checks["downstream_gold_target_retrieved_but_untested"] += int(bool(target) and target in retrieved and target not in tested)
            target_checks["downstream_rejected_positive_with_untested_candidates"] += int(untested > 0)
        downstream.append({"item_id": item_id, "text": r["text"],
                           "gold": "PUN" if gold[item_id] else "NON_PUN",
                           "target": l4.get("target_term"), "stage": stage,
                           "outcome": predictions["full_detection"][item_id],
                           "untested_terms": untested,
                           "l5_status": l5.get("resolution_status"),
                           "l6_status": l6.get("distinctness_status"),
                           "reason": l5.get("explanation") if stage == "L5" else l6.get("explanation")})
    times = Counter()
    for r in records:
        for t in r["trace"]:
            times[t["layer"]] += t.get("duration_ms", 0) / 1000
    searches = [r["l4_search"] for r in records if r.get("l4_search")]
    result = {"records_path": str(records_path.relative_to(ROOT)),
              "records_sha256": sha(records_path), "gold_sha256": sha(gold_path),
              "metrics": {name: metric(p, gold) for name, p in predictions.items()},
              "gate_transitions": changes, "downstream_rejections": downstream,
              "remaining_candidates": dict(remaining),
              "remaining_candidates_by_gold": dict(remaining_by_gold),
              "target_checks_exact_normalized": dict(target_checks),
              "summed_trace_seconds": dict(times),
              "candidate_search": {"records": len(searches),
                "mean_terms_assessed": statistics.mean(len(s["findings"]) for s in searches),
                "total_terms_assessed": sum(len(s["findings"]) for s in searches),
                "stop_reasons": dict(Counter(s["stop_reason"] for s in searches))}}
    if wrappers:
        usage = {}
        for r in raw:
            for e in r["api_events"]:
                stage = e["stage"]
                d = usage.setdefault(stage, {"calls": 0, "prompt_tokens": 0,
                    "completion_tokens": 0, "total_tokens": 0, "max_prompt_tokens": 0,
                    "message_counts": Counter(), "finish_reasons": Counter()})
                d["calls"] += 1
                u = (e.get("response") or {}).get("usage") or {}
                for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    d[key] += u.get(key, 0) or 0
                d["max_prompt_tokens"] = max(d["max_prompt_tokens"], u.get("prompt_tokens", 0) or 0)
                d["message_counts"][len(e.get("request", {}).get("messages", []))] += 1
                for choice in (e.get("response") or {}).get("choices", []):
                    d["finish_reasons"][str(choice.get("finish_reason"))] += 1
        total_tokens = sum(d["total_tokens"] for d in usage.values())
        for stage, d in usage.items():
            d["token_share"] = d["total_tokens"] / total_tokens
            d["message_counts"] = dict(d["message_counts"])
            d["finish_reasons"] = dict(d["finish_reasons"])
        result["observed_api_usage"] = usage
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-run", type=Path, default=ROOT / "runs/full_assignment_comparison/20261003T021452.992281Z/corrected_validation")
    parser.add_argument("--semeval-suite", type=Path, default=ROOT / "runs/semeval_benchmark/20261002T201740.595224Z")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/crack_stage_diagnosis_20261002.json")
    args = parser.parse_args()
    full_manifest = json.loads((args.full_run / "manifest.json").read_text())
    sem_manifest = json.loads((args.semeval_suite / "suite_manifest.json").read_text())
    source_a = full_manifest["production_fingerprint"]["source_sha256"]
    source_b = sem_manifest["source_sha256"]
    changed = [k for k in sorted(set(source_a) | set(source_b)) if source_a.get(k) != source_b.get(k)]
    if changed:
        raise ValueError(f"Cohort source snapshots differ: {changed}")
    a_config, b_config = full_manifest["crack_config"], sem_manifest["config"]
    for layer in ("L4", "L5", "L6"):
        model_a = a_config[f"{layer}_MODEL"] or a_config[f"{layer}_MODEL_OPENAI"]
        model_b = b_config[f"{layer}_MODEL"] or b_config[f"{layer}_MODEL_OPENAI"]
        if model_a != model_b:
            raise ValueError("Requested detection models differ")
    normalized_diffs = {}
    for k in sorted(set(a_config) | set(b_config)):
        a, b = a_config.get(k), b_config.get(k)
        if k.endswith("_MODEL"):
            a = a or a_config.get(k + "_OPENAI")
            b = b or b_config.get(k + "_OPENAI")
        if isinstance(a, list) and isinstance(b, list):
            a, b = sorted(a), sorted(b)
        if a != b:
            normalized_diffs[k] = [a, b]
    if normalized_diffs:
        raise ValueError(f"Effective configurations differ: {normalized_diffs}")
    sem_paths = list((args.semeval_suite / "detection").glob("*/records.jsonl"))
    if len(sem_paths) != 1:
        raise ValueError("Need one SemEval detection record file")
    result = {"method": "Offline recorded gate-prefix replay; no new inference, prompt, threshold, or gold change. Unresolved positives count as misses in full-gold F1. No explanations/ages are fabricated for prefix positives.",
              "limitations": ["Not a randomized causal ablation or an independent rerun.",
                "Removing L5 while retaining L6 cannot be evaluated for L5-rejected cases without new L6 inference.",
                "Detection gains from accepting weak targets do not establish full-task quality.",
                "Trace seconds are summed across concurrent items, not batch wall time."],
              "snapshot_alignment": {"source_files_identical": len(source_a),
                  "effective_config_differences": normalized_diffs,
                  "full_manifest_sha256": sha(args.full_run / "manifest.json"),
                  "semeval_manifest_sha256": sha(args.semeval_suite / "suite_manifest.json")},
              "full_assignment_60": audit(args.full_run / "crack/records.jsonl", args.full_run / "gold.jsonl", True),
              "semeval_2250": audit(sem_paths[0], args.semeval_suite / "inputs/detection_gold.jsonl")}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    for cohort in ("full_assignment_60", "semeval_2250"):
        print(cohort)
        for name, m in result[cohort]["metrics"].items():
            print(f"  {name}: accuracy={m['accuracy_all']:.4%}, F1={m['f1_full_gold']:.4%}, coverage={m['coverage']:.4%}; TP={m['tp']} FP={m['fp']} TN={m['tn']} FN={m['fn_decided']} unresolved={m['unresolved_positive']}/{m['unresolved_negative']}")
        print("  gate changes:", {k: v["counts"] for k, v in result[cohort]["gate_transitions"].items()})
        print("  untested:", result[cohort]["remaining_candidates"])
    print("Written:", args.output)


if __name__ == "__main__":
    main()
